"""
Table Index Module — DuckDB-backed structured table recall (§2.4.3).

Implements EAV (Entity-Attribute-Value) + wide-table dual mode for
querying structured XLSX/DOCX table data with SQL-like conditions.
"""

from __future__ import annotations

import json
import math
import operator
import re


_RESULT_COLUMNS = ('source_file', 'sheet_name', 'row_number', 'column_name',
                   'column_value', 'column_value_numeric', 'unit', 'context_json')
_CONDITION_TOKEN = re.compile(
    r'''\s*(?:('[^']*(?:''[^']*)*')|("[^"]*(?:""[^"]*)*")|'''
    r'''([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)|'''
    r'''([^\W\d]\w*)|(>=|<=|<>|!=|=|>|<|\(|\)))''')


def _validate_limit(top_k):
    if type(top_k) is not int or not 0 <= top_k <= 1000:
        raise ValueError('top_k must be an integer between 0 and 1000')


def _compile_conditions(conditions, columns):
    """Compile a bounded comparison grammar to DuckDB expressions, never SQL.

    Supports column/literal comparisons, IS [NOT] NULL, AND/OR and parentheses.
    Function calls, subqueries, comments and statements are deliberately absent.
    """
    import duckdb
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 32:
        raise ValueError('conditions must contain 1 to 32 predicates')
    comparisons = {'=': operator.eq, '!=': operator.ne, '<>': operator.ne,
                   '>': operator.gt, '>=': operator.ge, '<': operator.lt, '<=': operator.le}
    expressions = []
    for condition in conditions:
        if not isinstance(condition, str) or not condition.strip() or len(condition) > 2048:
            raise ValueError('invalid predicate size/type')
        tokens, offset = [], 0
        condition = condition.strip()
        while offset < len(condition):
            match = _CONDITION_TOKEN.match(condition, offset)
            if match is None or len(tokens) >= 256:
                raise ValueError('unsupported predicate syntax')
            kind, value = next((i, v) for i, v in enumerate(match.groups()) if v is not None)
            tokens.append((kind, value))
            offset = match.end()
        position = 0

        def take():
            nonlocal position
            if position >= len(tokens):
                raise ValueError('incomplete predicate')
            token = tokens[position]
            position += 1
            return token

        def peek(word):
            return position < len(tokens) and tokens[position][1].upper() == word

        def primary(depth):
            if depth > 16:
                raise ValueError('predicate nesting exceeds limit')
            if peek('('):
                take()
                result = expression(depth + 1)
                if take()[1] != ')':
                    raise ValueError('unbalanced predicate')
                return result
            kind, identifier = take()
            if kind not in (1, 3):
                raise ValueError('left operand must be a column')
            identifier = identifier[1:-1].replace('""', '"') if kind == 1 else identifier
            if identifier not in columns:
                raise ValueError('unknown predicate column')
            left = duckdb.ColumnExpression(identifier)
            if peek('IS'):
                take()
                negated = peek('NOT')
                if negated:
                    take()
                if take()[1].upper() != 'NULL':
                    raise ValueError('IS requires NULL')
                return left.isnotnull() if negated else left.isnull()
            operation = take()[1]
            if operation not in comparisons:
                raise ValueError('unsupported comparison')
            kind, literal = take()
            if kind == 0:
                value = literal[1:-1].replace("''", "'")
            elif kind == 2:
                value = float(literal)
                if not math.isfinite(value):
                    raise ValueError('nonfinite predicate number')
            else:
                raise ValueError('right operand must be a string or number literal')
            return comparisons[operation](left, duckdb.ConstantExpression(value))

        def conjunction(depth):
            result = primary(depth)
            while peek('AND'):
                take()
                result = result & primary(depth)
            return result

        def expression(depth):
            result = conjunction(depth)
            while peek('OR'):
                take()
                result = result | conjunction(depth)
            return result

        parsed = expression(0)
        if position != len(tokens):
            raise ValueError('unexpected predicate token')
        expressions.append(parsed)
    result = expressions[0]
    for expression_item in expressions[1:]:
        result = result & expression_item
    return result


class TableIndex:
    """DuckDB in-memory query engine for structured table recall.

    Ingests table-type chunks from Document Processor and provides
    SQL-like numerical condition filtering for metric queries.

    Dual mode:
    - EAV table: flexible single-column filtering (any schema)
    - Wide tables: per-sheet tables for multi-column SQL queries
    """

    def __init__(self):
        try:
            import duckdb
        except ImportError:
            raise ImportError("duckdb is required for TableIndex. Install: pip install duckdb")

        self.conn = duckdb.connect(":memory:")

        # EAV table — universal schema for any table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS table_rows (
                row_id VARCHAR PRIMARY KEY,
                source_file VARCHAR,
                source_format VARCHAR,
                sheet_name VARCHAR,
                row_number INTEGER,
                column_name VARCHAR,
                column_value VARCHAR,
                column_value_numeric DOUBLE,
                unit VARCHAR,
                context_json VARCHAR
            )
        """)

        self._wide_tables_created: set[str] = set()

    # ── Ingest ──────────────────────────────────────────────────────────

    def ingest_section(self, section: dict):
        """Ingest a table-type section from Document Processor.

        Args:
            section: Dict with keys: chunk_id, metadata, table_json, sheet_name.
                     table_json: {headers: [...], rows: [[...], ...]}
        """
        table = section.get("table_json")
        if not table:
            return

        headers = table.get("headers", [])
        rows = table.get("rows", [])
        if not headers or not rows:
            return

        source_file = ""
        source_format = ""
        if section.get("metadata"):
            source_file = section["metadata"].get("source_file", "")
            source_format = section["metadata"].get("source_format", "")

        sheet_name = section.get("sheet_name", table.get("sheet_name", source_file))
        chunk_id = section.get("chunk_id", "")

        # Insert into EAV table
        for row_idx, row in enumerate(rows):
            context = dict(zip(headers, row))
            for col_idx, cell_value in enumerate(row):
                if col_idx >= len(headers):
                    break
                col_name = headers[col_idx]
                str_value = str(cell_value) if cell_value is not None else ""
                num_value = _parse_numeric(str_value)
                unit = _infer_unit(col_name, str_value)

                self.conn.execute("""
                    INSERT OR REPLACE INTO table_rows
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{chunk_id}_{row_idx}_{col_idx}",
                    source_file,
                    source_format,
                    sheet_name,
                    row_idx,
                    col_name,
                    str_value,
                    num_value,
                    unit,
                    json.dumps(context, ensure_ascii=False),
                ))

        # Create wide table for multi-column queries
        clean_sheet = _sanitize_name(sheet_name)
        if clean_sheet not in self._wide_tables_created and len(headers) >= 2:
            self._create_wide_table(clean_sheet, headers, rows)

    def ingest_chunks(self, chunks: list):
        """Ingest all table-type chunks from a list of Chunk objects."""
        for chunk in chunks:
            if chunk.content_type in ("table", "mixed") and chunk.table_json:
                section = {
                    "chunk_id": chunk.chunk_id,
                    "metadata": {
                        "source_file": chunk.metadata.source_file if chunk.metadata else "",
                        "source_format": chunk.metadata.source_format if chunk.metadata else "",
                    },
                    "table_json": chunk.table_json,
                }
                self.ingest_section(section)

    # ── Query ───────────────────────────────────────────────────────────

    def query(
        self,
        conditions: list[str] | None = None,
        top_k: int = 20,
        prefer_wide: bool = True,
    ) -> list[dict]:
        """Execute structured query on table data.

        Args:
            conditions: List of SQL-like condition strings.
                e.g. ["column_name = '预算执行率' AND column_value_numeric > 0.8"]
            top_k: Maximum results.

        Returns:
            List of matched row dicts with source_file, sheet_name, row_number, etc.
        """
        _validate_limit(top_k)
        if not conditions:
            return self._recent_rows(top_k)
        columns = set(self.conn.table('table_rows').columns)
        for table_name in self._wide_tables_created:
            columns.update(self.conn.table(table_name).columns)
        predicate = _compile_conditions(conditions, columns)
        try:
            result = (self.conn.table('table_rows').filter(predicate)
                      .project(', '.join(_RESULT_COLUMNS)).distinct()
                      .order('column_value_numeric DESC NULLS LAST').limit(top_k).fetchall())
            if result:
                return self._rows_to_dicts(result)
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass
        if prefer_wide:
            return self._query_wide_tables(conditions, top_k)
        return []

    def _recent_rows(self, top_k: int) -> list[dict]:
        """Return most recently ingested rows (fallback when no conditions)."""
        _validate_limit(top_k)
        result = (self.conn.table('table_rows').project(', '.join(_RESULT_COLUMNS))
                  .distinct().limit(top_k).fetchall())
        return self._rows_to_dicts(result)

    def _rows_to_dicts(self, rows: list) -> list[dict]:
        """Convert DuckDB rows to dicts."""
        if not rows:
            return []
        return [
            {
                "source_file": r[0],
                "sheet_name": r[1],
                "row_number": r[2],
                "column_name": r[3],
                "column_value": r[4],
                "column_value_numeric": r[5],
                "unit": r[6],
                "context": json.loads(r[7]) if r[7] else {},
            }
            for r in rows
        ]

    def export_rows(self) -> list[dict]:
        """Return a full snapshot of indexed EAV rows for recovery/debug recall paths."""
        result = self.conn.execute(
            """
            SELECT DISTINCT source_file, sheet_name, row_number,
                   column_name, column_value, column_value_numeric, unit,
                   context_json
            FROM table_rows
            ORDER BY row_number ASC
            """
        ).fetchall()
        return self._rows_to_dicts(result)

    # ── Wide Table Support ──────────────────────────────────────────────

    def _create_wide_table(self, sheet_name: str, headers: list[str], rows: list[list]):
        """Create a wide table (original column structure) for multi-column SQL."""
        if not headers or len(headers) < 2:
            return

        safe_name = _sanitize_name(sheet_name)

        # Drop existing if re-ingesting
        self.conn.execute(f'DROP TABLE IF EXISTS "{safe_name}"')

        col_defs = ", ".join(f'"{_sanitize_name(h)}" VARCHAR' for h in headers if h)
        self.conn.execute(f'CREATE TABLE "{safe_name}" ({col_defs})')

        for row in rows:
            values = [str(cell) if cell is not None else "" for cell in row[:len(headers)]]
            # Pad short rows
            while len(values) < len(headers):
                values.append("")
            self.conn.table(safe_name).insert(values)

        self._wide_tables_created.add(safe_name)

    def _query_wide_tables(self, conditions: list[str], top_k: int) -> list[dict]:
        """Search wide tables for matching rows."""
        import duckdb
        _validate_limit(top_k)
        results = []
        for table_name in list(self._wide_tables_created)[:10]:  # limit search
            try:
                relation = self.conn.table(table_name)
                predicate = _compile_conditions(conditions, set(relation.columns))
                projection = [duckdb.ColumnExpression(c) for c in relation.columns]
                rows = relation.filter(predicate).project(
                    *projection, duckdb.ConstantExpression(table_name).alias('_source')
                ).limit(top_k).fetchall()
                for r in rows:
                    results.append({
                        "source_file": "",
                        "sheet_name": r[-1] if r else table_name,
                        "row_number": 0,
                        "column_name": "",
                        "column_value": json.dumps(r[:-1], ensure_ascii=False),
                        "column_value_numeric": None,
                        "unit": "",
                        "context": {},
                    })
            except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                continue

        return results[:top_k]

    # ── Stats ───────────────────────────────────────────────────────────

    def count(self) -> int:
        """Total rows in EAV table."""
        result = self.conn.execute("SELECT COUNT(*) FROM table_rows").fetchone()
        return result[0] if result else 0

    def sheet_count(self) -> int:
        """Number of unique sheets ingested."""
        result = self.conn.execute(
            "SELECT COUNT(DISTINCT sheet_name) FROM table_rows"
        ).fetchone()
        return result[0] if result else 0

    def get_stats(self) -> dict:
        """Return table index statistics for health checks."""
        return {
            "total_rows": self.count(),
            "unique_sheets": self.sheet_count(),
            "wide_tables": len(self._wide_tables_created),
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_numeric(value: str) -> float | None:
    """Try to parse a string as a number, handling percentages and units."""
    if not value:
        return None

    # Try direct float
    try:
        return float(value)
    except ValueError:
        pass

    # Percentage: "84%" → 0.84, "84.5%" → 0.845
    pct_match = re.match(r'^([\d.]+)\s*%$', value)
    if pct_match:
        return float(pct_match.group(1)) / 100.0

    # Number with unit suffix: "50万元" → 50
    num_match = re.match(r'^([\d.]+)\s*[万亿千百]?\s*(元|万元|亿|美元|人等|个|项|天|月|年|次)?$', value)
    if num_match:
        return float(num_match.group(1))

    return None


def _infer_unit(column_name: str, value: str) -> str:
    """Infer unit from column name and value string."""
    # Check value for embedded unit
    for unit in ["%", "元", "万元", "亿美元", "人", "个", "项", "天", "月", "年"]:
        if unit in value:
            return unit

    # Check column name hints
    col_lower = column_name.lower()
    if "率" in col_lower or "rate" in col_lower or "percent" in col_lower:
        return "%"
    if "金额" in col_lower or "预算" in col_lower or "金额" in col_lower:
        return "万元"
    if "人数" in col_lower or "员工" in col_lower:
        return "人"

    return ""


def _sanitize_name(name: str) -> str:
    """Sanitize a sheet/column name for use as SQL identifier."""
    # Remove special chars, replace spaces
    safe = re.sub(r'[^\w]', '_', name)
    if safe and safe[0].isdigit():
        safe = "t_" + safe
    return safe or "unnamed"
