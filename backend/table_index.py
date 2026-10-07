"""
Table Index Module — DuckDB-backed structured table recall (§2.4.3).

Implements EAV (Entity-Attribute-Value) + wide-table dual mode for
querying structured XLSX/DOCX table data with SQL-like conditions.
"""

from __future__ import annotations

import json
import re


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
        if not conditions:
            return self._recent_rows(top_k)

        where_clause = " AND ".join(f"({c})" for c in conditions) if conditions else "1=1"

        # Try wide tables first, fall back to EAV
        sql = f"""
            SELECT DISTINCT source_file, sheet_name, row_number,
                   column_name, column_value, column_value_numeric, unit,
                   context_json
            FROM table_rows
            WHERE {where_clause}
            ORDER BY column_value_numeric DESC NULLS LAST
            LIMIT {top_k}
        """

        try:
            result = self.conn.execute(sql).fetchall()
            if result:
                return self._rows_to_dicts(result)

            # Also search wide tables
            wide_results = self._query_wide_tables(conditions, top_k)
            if wide_results:
                return wide_results

        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        return []

    def _recent_rows(self, top_k: int) -> list[dict]:
        """Return most recently ingested rows (fallback when no conditions)."""
        sql = f"""
            SELECT DISTINCT source_file, sheet_name, row_number,
                   column_name, column_value, column_value_numeric, unit,
                   context_json
            FROM table_rows
            LIMIT {top_k}
        """
        result = self.conn.execute(sql).fetchall()
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

        placeholders = ", ".join("?" for _ in headers)
        for row in rows:
            values = [str(cell) if cell is not None else "" for cell in row[:len(headers)]]
            # Pad short rows
            while len(values) < len(headers):
                values.append("")
            self.conn.execute(f'INSERT INTO "{safe_name}" VALUES ({placeholders})', values)

        self._wide_tables_created.add(safe_name)

    def _query_wide_tables(self, conditions: list[str], top_k: int) -> list[dict]:
        """Search wide tables for matching rows."""
        results = []
        for table_name in list(self._wide_tables_created)[:10]:  # limit search
            try:
                where = " AND ".join(f"({c})" for c in conditions)
                sql = f'SELECT *, \'{table_name}\' as _source FROM "{table_name}" WHERE {where} LIMIT {top_k}'
                rows = self.conn.execute(sql).fetchall()
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
