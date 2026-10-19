import sys
import pytest
from index_registry import build_bm25_from_chunks
from doc_processor import Chunk

class Reader:
    def __init__(self, exc):
        self.exc = exc
        self.closed = False
    def __iter__(self):
        return self
    def __next__(self):
        raise self.exc
    def close(self):
        self.closed = True

@pytest.mark.parametrize('exc', [RuntimeError('first read failed'), StopIteration()])
def test_first_read_always_closes(exc):
    reader = Reader(exc)
    if isinstance(exc, StopIteration):
        assert build_bm25_from_chunks(reader) is None
    else:
        with pytest.raises(RuntimeError, match='first read failed'):
            build_bm25_from_chunks(reader)
    assert reader.closed

def test_rag_no_capabilities_preserves_none():
    from routes.rag_query import _build_bm25_index_from_vector_store
    assert _build_bm25_index_from_vector_store(object()) is None

def test_rag_page_only_supported():
    from routes.rag_query import _build_bm25_index_from_vector_store
    class Pages:
        closed = False
        def iter_record_pages(self, page_size):
            try:
                yield {'ids': ['x'], 'documents': ['alpha beta'], 'metadatas': [{}]}
            finally:
                self.closed = True
    store = Pages()
    assert _build_bm25_index_from_vector_store(store)[1][0].chunk_id == 'x'
    assert store.closed

@pytest.mark.parametrize('entry', ['build', 'eval'])
@pytest.mark.parametrize('has_table', [True, False])
def test_missing_rank_all_entries(entry, has_table, monkeypatch):
    import table_index
    from test_r8_paged_consumers import SQLitePages
    received = []
    original = table_index.TableIndex.ingest_chunks
    def observe(self, chunks):
        received.extend(c.chunk_id for c in chunks)
        return original(self, chunks)
    monkeypatch.setattr(table_index.TableIndex, 'ingest_chunks', observe)
    monkeypatch.setitem(sys.modules, 'rank_bm25', None)
    if entry == 'build':
        from build_indices import build_indices as build
    else:
        from run_evaluation import build_optional_indices as build
    store = SQLitePages(19, table=has_table)
    bm25, tables = build(store)
    assert bm25 is None
    assert received == (['18'] if has_table else [str(i) for i in range(19)])
    assert store.closed

def test_misaligned_page_closes():
    from paged_chunks import iter_store_chunks
    class Broken:
        closed = False
        def iter_record_pages(self, page_size):
            try:
                yield {'ids': ['a'], 'documents': [], 'metadatas': [{}]}
            finally:
                self.closed = True
    store = Broken()
    with pytest.raises(ValueError, match='列长度'):
        list(iter_store_chunks(store))
    assert store.closed
