import pytest
from test_independent_edges import Reader
from index_registry import build_bm25_from_chunks
from doc_processor import Chunk

def test_missing_rank_does_not_touch_or_close_input(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'rank_bm25', None)
    reader = Reader(AssertionError('must not consume'))
    assert build_bm25_from_chunks(reader) is None
    assert not reader.closed

def test_normal_completion_closes_exactly_once():
    class Items:
        closes=0
        def __init__(self): self.items=iter([Chunk(chunk_id='one', text='alpha beta', content_type='text')])
        def __iter__(self): return self
        def __next__(self): return next(self.items)
        def close(self): self.closes += 1
    items=Items()
    result=build_bm25_from_chunks(items)
    assert result[1][0].chunk_id=='one'
    assert items.closes==1

def test_noncallable_page_capability_preserves_rag_none():
    from routes.rag_query import _build_bm25_index_from_vector_store
    class NoPages: iter_record_pages=None
    assert _build_bm25_index_from_vector_store(NoPages()) is None

