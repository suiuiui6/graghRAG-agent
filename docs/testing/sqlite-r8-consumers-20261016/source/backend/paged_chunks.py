"""Snapshot pages for candidates; explicit full-read legacy Chroma fallback."""
from doc_processor import Chunk


def iter_store_chunks(store, page_size=256):
    pages_method = getattr(store, 'iter_record_pages', None)
    if callable(pages_method):
        pages = iter(pages_method(page_size=page_size))
    else:
        # Chroma has no stable offset snapshot. Keep its old single-get semantics.
        pages = iter((store._collection.get(include=['documents', 'metadatas']),))
    try:
        for page in pages:
            ids = page.get('ids') or []
            documents = page.get('documents') or []
            metadatas = page.get('metadatas') or []
            if len(ids) != len(documents) or len(ids) != len(metadatas):
                raise ValueError('分页记录列长度不一致')
            for chunk_id, text, metadata in zip(ids, documents, metadatas):
                yield Chunk(chunk_id, text or '', (metadata or {}).get('content_type', 'text'))
    finally:
        close = getattr(pages, 'close', None)
        if close is not None:
            close()
