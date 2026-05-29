"""Shared state between route modules — JSON-persisted document store."""

import json, os, threading

_BASE = os.path.dirname(os.path.dirname(__file__))
DOCS_JSON_PATH = os.path.join(_BASE, "output", "docs_store.json")
_lock = threading.Lock()

# Shared query counter (thread-safe)
query_count = 0
_counter_lock = threading.Lock()


def increment_query_count():
    global query_count
    with _counter_lock:
        query_count += 1


def get_query_count() -> int:
    global query_count
    with _counter_lock:
        return query_count

def _load_docs() -> list[dict]:
    """Load documents from JSON file. Returns empty list if file missing/corrupt — no default seed."""
    if os.path.exists(DOCS_JSON_PATH):
        try:
            with open(DOCS_JSON_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_docs(docs: list[dict]):
    """Persist documents to JSON file."""
    os.makedirs(os.path.dirname(DOCS_JSON_PATH), exist_ok=True)
    with open(DOCS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


_docs_store: list[dict] = _load_docs()


def add_doc(doc: dict):
    """Thread-safe add document."""
    with _lock:
        _docs_store.append(doc)
        _save_docs(_docs_store)


def remove_doc(doc_id: str):
    """Thread-safe remove document."""
    global _docs_store
    with _lock:
        _docs_store = [d for d in _docs_store if d["document_id"] != doc_id]
        _save_docs(_docs_store)


def get_docs_snapshot() -> list[dict]:
    """Thread-safe read — returns a shallow copy of the current document store."""
    with _lock:
        return _docs_store[:]
