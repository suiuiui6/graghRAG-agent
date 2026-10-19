"""Build BM25 and table indices from a single snapshot chunk stream."""
from index_registry import (build_bm25_from_chunks, build_table_index_from_chunks,
                            set_bm25_index, set_table_index)
from paged_chunks import iter_store_chunks


def build_indices(vector_store, bm25_index=None, table_index=None):
    chunks = iter_store_chunks(vector_store)
    try:
        if bm25_index is None:
            bm25_index = build_bm25_from_chunks(chunks)
            all_chunks = bm25_index[1] if bm25_index is not None else list(chunks)
            if bm25_index is not None:
                set_bm25_index(bm25_index)
        else:
            all_chunks = list(chunks)
        if table_index is None:
            table_chunks = [c for c in all_chunks
                            if c.content_type == "table" or "<table>" in c.text.lower()]
            table_index = build_table_index_from_chunks(table_chunks or all_chunks)
            if table_index is not None:
                set_table_index(table_index)
        return bm25_index, table_index
    finally:
        chunks.close()


def main():
    from vector_store import VectorStore
    bm25, table = build_indices(VectorStore())
    print(f"BM25 文档数：{len(bm25[1]) if bm25 else 0}")
    print(f"表格索引行数：{table.count() if table else 0}")


if __name__ == "__main__":
    main()
