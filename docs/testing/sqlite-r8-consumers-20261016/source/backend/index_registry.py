"""
Shared index registry — global references for BM25 + TableIndex.

These are built at ingest time and consumed by the retrieval pipeline.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # rank_bm25 在 build_bm25_from_chunks 内按需导入（软依赖，缺失时有 bigram fallback），
    # 但返回类型注解 "BM25Okapi | None" 需要该名字可解析（否则 ruff F821 悬空引用）。
    from rank_bm25 import BM25Okapi

ARTIFACTS_DIR = Path(os.environ.get('GRAPHRAG_RUNTIME_ARTIFACTS_DIR')
                     or Path(__file__).resolve().parent / "output" / "runtime")
BM25_ARTIFACT_PATH = ARTIFACTS_DIR / "bm25_artifact.json"
TABLE_ARTIFACT_PATH = ARTIFACTS_DIR / "table_artifact.json"

# Global index instances (built at ingest time, read at query time)
_bm25_index = None
_table_index = None
_bm25_lock = threading.Lock()
_table_lock = threading.Lock()


class RestoredTableIndex:
    """Minimal table index fallback restored from serialized rows."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = list(rows or [])

    def query(self, conditions: list[str] | None = None, top_k: int = 20, prefer_wide: bool = True) -> list[dict]:
        if conditions:
            return []
        return self.rows[:top_k]

    def get_stats(self) -> dict:
        return {
            "total_rows": len(self.rows),
            "unique_sheets": len({row.get("sheet_name", "") for row in self.rows if row.get("sheet_name")}),
            "wide_tables": 0,
            "restored": True,
        }

    def export_rows(self) -> list[dict]:
        """Snapshot every restored row independently of interactive query limits."""
        return list(self.rows)


def get_bm25_index():
    """Return the current global BM25 index (may be None if not yet built)."""
    global _bm25_index
    with _bm25_lock:
        return _bm25_index


def set_bm25_index(index, persist: bool = True):
    """Set the global BM25 index (called after ingest completes)."""
    global _bm25_index
    with _bm25_lock:
        _bm25_index = index
    if persist:
        try:
            snapshot_bm25_index(index=index)
        except Exception:  # noqa: S110, BLE001  # Windows 文件锁容忍：目标被占用时跳过，不终止进程
            pass
    try:
        from routes.rag_query import invalidate_rag_runtime

        invalidate_rag_runtime()
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass


def get_table_index():
    """Return the current global TableIndex (may be None if not yet built)."""
    global _table_index
    with _table_lock:
        return _table_index


def set_table_index(index, persist: bool = True):
    """Set the global TableIndex (called after ingest completes)."""
    global _table_index
    with _table_lock:
        _table_index = index
    if persist:
        try:
            snapshot_table_index(index=index)
        except Exception:  # noqa: S110, BLE001  # Windows 文件锁容忍：目标被占用时跳过，不终止进程
            pass
    try:
        from routes.rag_query import invalidate_rag_runtime

        invalidate_rag_runtime()
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass


def persist_bm25_artifact(path: Path, payload: dict) -> None:
    _persist_json_artifact(path, payload)


def restore_bm25_artifact(path: Path) -> dict | None:
    return _restore_json_artifact(path)


def persist_table_artifact(path: Path, payload: dict) -> None:
    _persist_json_artifact(path, payload)


def restore_table_artifact(path: Path) -> dict | None:
    return _restore_json_artifact(path)


def snapshot_bm25_index(path: Path | None = None, index=None) -> dict | None:
    target = Path(path) if path else BM25_ARTIFACT_PATH
    payload = _serialize_bm25_index(index if index is not None else get_bm25_index())
    if payload is None:
        return None
    persist_bm25_artifact(target, payload)
    return payload


def snapshot_table_index(path: Path | None = None, index=None) -> dict | None:
    target = Path(path) if path else TABLE_ARTIFACT_PATH
    payload = _serialize_table_index(index if index is not None else get_table_index())
    if payload is None:
        return None
    persist_table_artifact(target, payload)
    return payload


def restore_runtime_indexes(
    bm25_path: Path | None = None,
    table_path: Path | None = None,
) -> dict[str, dict]:
    bm25_artifact_path = Path(bm25_path) if bm25_path else BM25_ARTIFACT_PATH
    table_artifact_path = Path(table_path) if table_path else TABLE_ARTIFACT_PATH
    result = {
        "bm25": {"artifact_path": str(bm25_artifact_path), "restored": False, "reason": "not_found"},
        "table": {"artifact_path": str(table_artifact_path), "restored": False, "reason": "not_found"},
    }

    try:
        bm25_payload = restore_bm25_artifact(bm25_artifact_path)
        if bm25_payload:
            restored_bm25 = _deserialize_bm25_index(bm25_payload)
            if restored_bm25 is not None:
                set_bm25_index(restored_bm25, persist=False)
                result["bm25"] = {"artifact_path": str(bm25_artifact_path), "restored": True, "reason": "ok"}
            else:
                result["bm25"] = {"artifact_path": str(bm25_artifact_path), "restored": False, "reason": "invalid_payload"}
    except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
        result["bm25"] = {"artifact_path": str(bm25_artifact_path), "restored": False, "reason": "invalid_payload"}

    try:
        table_payload = restore_table_artifact(table_artifact_path)
        if table_payload:
            restored_table = _deserialize_table_index(table_payload)
            if restored_table is not None:
                set_table_index(restored_table, persist=False)
                result["table"] = {"artifact_path": str(table_artifact_path), "restored": True, "reason": "ok"}
            else:
                result["table"] = {"artifact_path": str(table_artifact_path), "restored": False, "reason": "invalid_payload"}
    except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
        result["table"] = {"artifact_path": str(table_artifact_path), "restored": False, "reason": "invalid_payload"}

    return result


def get_runtime_recovery_status(
    bm25_path: Path | None = None,
    table_path: Path | None = None,
) -> dict[str, dict]:
    bm25_artifact_path = Path(bm25_path) if bm25_path else BM25_ARTIFACT_PATH
    table_artifact_path = Path(table_path) if table_path else TABLE_ARTIFACT_PATH
    bm25_index = get_bm25_index()
    table_index = get_table_index()
    return {
        "bm25": {
            "artifact_path": str(bm25_artifact_path),
            "artifact_exists": bm25_artifact_path.exists(),
            "loaded": bm25_index is not None,
        },
        "table": {
            "artifact_path": str(table_artifact_path),
            "artifact_exists": table_artifact_path.exists(),
            "loaded": table_index is not None,
        },
    }


def build_bm25_from_chunks(chunks) -> "BM25Okapi | None":
    """Build BM25 from one pass over Chunk objects, retaining final chunks only.

    Uses jieba for Chinese tokenization; falls back to character-level
    bigrams if jieba is unavailable. Returns a tuple of
    (BM25Okapi, list_of_chunks) for score resolution.
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return None

    from itertools import chain
    iterator = iter(chunks)
    try:
        first = next(iterator)
    except StopIteration:
        return None
    retained = chunks if isinstance(chunks, list) else []

    def tokens():
        for chunk in chain((first,), iterator):
            if retained is not chunks:
                retained.append(chunk)
            yield _tokenize_for_bm25(chunk.text)

    try:
        return (BM25Okapi(tokens()), retained)
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()



def _tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize text for BM25 indexing with Chinese language support.

    Uses jieba for Chinese segmentation when available; falls back to
    character bigrams (which work better than whitespace-split for CJK).
    """
    text = text.lower().strip()
    if not text:
        return []

    try:
        import jieba
        tokens = [t.strip() for t in jieba.cut(text) if t.strip()]
        if tokens:
            return tokens
    except ImportError:
        pass

    return _fallback_tokenize_for_bm25(text)


def _fallback_tokenize_for_bm25(text: str) -> list[str]:
    """Fallback tokenizer for environments without jieba."""
    # Fallback: character bigrams for CJK + whitespace-split for ASCII
    tokens = []
    buf = ""
    for ch in text:
        if ch >= '一' and ch <= '鿿':  # CJK range
            if buf:
                tokens.extend(buf.split())
                buf = ""
            tokens.append(ch)
        elif ch.isspace():
            if buf:
                tokens.extend(buf.split())
                buf = ""
        else:
            buf += ch
    if buf:
        tokens.extend(buf.split())

    # Build character bigrams for CJK sequences
    result = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and _is_cjk(tokens[i]) and _is_cjk(tokens[i + 1]):
            result.append(tokens[i] + tokens[i + 1])
            i += 1
        else:
            result.append(tokens[i])
            i += 1
    return result


def _is_cjk(ch: str) -> bool:
    return len(ch) == 1 and '一' <= ch <= '鿿'


def build_table_index_from_chunks(chunks: list):
    """Build a TableIndex from table-type chunks."""
    try:
        from table_index import TableIndex

        ti = TableIndex()
        ti.ingest_chunks(chunks)
        return ti
    except ImportError:
        return None
    except Exception:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        return None


def _persist_json_artifact(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _restore_json_artifact(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _serialize_bm25_index(index) -> dict | None:
    if not isinstance(index, tuple) or len(index) != 2:
        return None
    _, chunks = index
    return {
        "chunks": [_serialize_chunk(chunk) for chunk in chunks],
    }


def _deserialize_bm25_index(payload: dict):
    if not isinstance(payload, dict):
        return None
    chunk_payloads = payload.get("chunks", [])
    if not isinstance(chunk_payloads, list) or not chunk_payloads:
        return None
    chunks = []
    for idx, item in enumerate(chunk_payloads):
        if not isinstance(item, (dict, str)):
            return None
        chunks.append(_deserialize_chunk(item, idx))
    return build_bm25_from_chunks(chunks)


def _serialize_table_index(index) -> dict | None:
    if index is None:
        return None
    export = getattr(index, 'export_rows', None)
    if callable(export):
        try:
            rows = export()
        except Exception:  # noqa: BLE001  # Preserve the last valid snapshot on read failure.
            return None
        return {"rows": rows} if isinstance(rows, list) else None
    try:
        rows = index.query(top_k=5000)
    except TypeError:
        try:
            rows = index.query(None, 5000)
        except Exception:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            return None
    except Exception:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        return None
    return {"rows": rows} if isinstance(rows, list) else None


def _deserialize_table_index(payload: dict):
    if not isinstance(payload, dict):
        return None
    rows = payload.get("rows")
    if rows is None or not isinstance(rows, list):
        return None
    return RestoredTableIndex(rows)


def _serialize_chunk(chunk) -> dict:
    metadata = getattr(chunk, "metadata", None)
    return {
        "chunk_id": getattr(chunk, "chunk_id", ""),
        "text": getattr(chunk, "text", str(chunk) if isinstance(chunk, str) else ""),
        "source_file": getattr(metadata, "source_file", "") if metadata else "",
    }


def _deserialize_chunk(payload, idx: int):
    if isinstance(payload, str):
        return SimpleNamespace(
            chunk_id=f"restored_bm25_{idx}",
            text=payload,
            metadata=SimpleNamespace(source_file=""),
        )

    return SimpleNamespace(
        chunk_id=payload.get("chunk_id", f"restored_bm25_{idx}"),
        text=payload.get("text", ""),
        metadata=SimpleNamespace(source_file=payload.get("source_file", "")),
    )
