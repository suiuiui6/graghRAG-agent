import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['GRAPHRAG_RUNTIME_ARTIFACTS_DIR'] = str(ROOT / 'test-output')

from doc_processor import Chunk
from index_registry import build_bm25_from_chunks, _tokenize_for_bm25


class SQLitePages:
    """Real SQLite snapshot source; forbidden get catches full-read bypasses."""
    def __init__(self, count=137, table=False):
        self.path = ROOT / f'test-{uuid4().hex}.sqlite'
        self.pages = 0
        self.closed = False
        self._collection = self
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE chunks(id INTEGER PRIMARY KEY, text TEXT, kind TEXT)')
            db.executemany('INSERT INTO chunks VALUES (?, ?, ?)', [
                (i, f'alpha beta item{i}', 'table' if table and i == count-1 else 'text')
                for i in range(count)
            ])

    def get(self, **kwargs):
        raise AssertionError('candidate must not call full collection.get')

    def iter_record_pages(self, page_size=256):
        db = sqlite3.connect(self.path)
        try:
            db.execute('BEGIN')
            cursor = db.execute('SELECT id,text,kind FROM chunks ORDER BY id')
            while rows := cursor.fetchmany(min(page_size, 17)):
                self.pages += 1
                yield {'ids': [str(r[0]) for r in rows],
                       'documents': [r[1] for r in rows],
                       'metadatas': [{'content_type': r[2]} for r in rows]}
        finally:
            db.close()
            self.closed = True


@pytest.mark.parametrize('entry', ['rag', 'build', 'eval'])
@pytest.mark.parametrize('count', [0, 137])
def test_three_consumers(entry, count):
    store = SQLitePages(count)
    if entry == 'rag':
        from routes.rag_query import _build_bm25_index_from_vector_store
        result = _build_bm25_index_from_vector_store(store)
    elif entry == 'build':
        from build_indices import build_indices
        result, _ = build_indices(store)
    else:
        from run_evaluation import build_optional_indices
        result, _ = build_optional_indices(store, bm25_index=None, table_index=None)
    assert store.closed
    if count == 0:
        assert result is None
    else:
        assert store.pages == 9
        assert [c.chunk_id for c in result[1]] == [str(i) for i in range(count)]
        assert result[1][-1].text == 'alpha beta item136'
        old = BM25Okapi([_tokenize_for_bm25(c.text) for c in result[1]])
        np.testing.assert_array_equal(result[0].get_scores(['alpha', 'item136']),
                                      old.get_scores(['alpha', 'item136']))


def test_single_pass_bm25_iterable():
    chunks = [Chunk(str(i), f'alpha item{i}', 'text') for i in range(137)]
    result = build_bm25_from_chunks(iter(chunks))
    assert isinstance(result[1], list)
    assert result[1] == chunks


def test_empty_generator():
    assert build_bm25_from_chunks(iter(())) is None


def test_snapshot_concurrent_write_and_early_close():
    from paged_chunks import iter_store_chunks
    store = SQLitePages()
    chunks = iter_store_chunks(store, page_size=17)
    assert next(chunks).chunk_id == '0'
    with sqlite3.connect(store.path) as db:
        db.execute('DELETE FROM chunks WHERE id=136')
        db.execute("INSERT INTO chunks VALUES (200, 'new text', 'text')")
    rest = list(chunks)
    assert rest[-1].chunk_id == '136'
    assert len(rest) == 136
    assert store.closed
    store.closed = False
    chunks = iter_store_chunks(store)
    next(chunks)
    chunks.close()
    assert store.closed


@pytest.mark.parametrize('entry', ['rag', 'build', 'eval'])
def test_error_closes_snapshot(entry):
    # Text has wrong type; real tokenizer raises while SQLite reader is open.
    store = SQLitePages()
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE chunks SET text=x'00' WHERE id=18")
    if entry == 'rag':
        from routes.rag_query import _build_bm25_index_from_vector_store as build
    elif entry == 'build':
        from build_indices import build_indices as build
    else:
        from run_evaluation import build_optional_indices as build
    with pytest.raises(TypeError):
        build(store)
    assert store.closed


@pytest.mark.parametrize('table', [True, False])
@pytest.mark.parametrize('entry', ['build', 'eval'])
def test_table_selection_preserves_complete_fallback(table, entry, monkeypatch):
    import table_index
    original = table_index.TableIndex.ingest_chunks
    received = []

    def observe(self, chunks):
        received.extend(c.chunk_id for c in chunks)
        return original(self, chunks)

    monkeypatch.setattr(table_index.TableIndex, 'ingest_chunks', observe)
    store = SQLitePages(table=table)
    if entry == 'build':
        from build_indices import build_indices as build
    else:
        from run_evaluation import build_optional_indices as build
    bm25, tables = build(store)
    assert received == (['136'] if table else [str(i) for i in range(137)])
    assert len(bm25[1]) == 137
    assert tables.count() == 0  # Legacy flat metadata carries no table_json.


def test_existing_indices_skip_scan():
    from run_evaluation import build_optional_indices
    store = SQLitePages()
    left, right = object(), object()
    assert build_optional_indices(store, left, right) == (left, right)
    assert store.pages == 0


def test_rank_receives_single_pass_tokens(monkeypatch):
    import rank_bm25
    original = rank_bm25.BM25Okapi

    def inspect(corpus, *args, **kwargs):
        assert iter(corpus) is corpus
        assert not kwargs.get('tokenizer')
        return original(corpus, *args, **kwargs)

    monkeypatch.setattr(rank_bm25, 'BM25Okapi', inspect)
    result = build_bm25_from_chunks(iter([Chunk('a', 'alpha beta', 'text')]))
    assert result[0].corpus_size == 1


def test_legacy_fallback_single_get_without_fake_offset():
    from paged_chunks import iter_store_chunks
    class Legacy:
        calls = 0
        def __init__(self):
            self._collection = self
        def get(self, **kwargs):
            self.calls += 1
            assert kwargs == {'include': ['documents', 'metadatas']}
            return {'ids': ['a', 'b'], 'documents': ['alpha', 'beta'],
                    'metadatas': [None, {'content_type': 'table'}]}
    store = Legacy()
    result = list(iter_store_chunks(store))
    assert [(c.chunk_id, c.content_type) for c in result] == [('a', 'text'), ('b', 'table')]
    assert store.calls == 1


def test_missing_rank_still_consumes_complete_table_fallback(monkeypatch):
    import table_index
    from build_indices import build_indices
    original = table_index.TableIndex.ingest_chunks
    received = []
    def observe(self, chunks):
        received.extend(c.chunk_id for c in chunks)
        return original(self, chunks)
    monkeypatch.setattr(table_index.TableIndex, 'ingest_chunks', observe)
    monkeypatch.setitem(sys.modules, 'rank_bm25', None)
    store = SQLitePages()
    model, tables = build_indices(store)
    assert model is None
    assert received == [str(i) for i in range(137)]
    assert store.closed
