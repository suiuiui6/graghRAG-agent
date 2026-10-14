"""
Build BM25 + TableIndex from existing vector store chunks.

This fills the gap where PDF ingest doesn't build these indices
(unlike DOCX/XLSX ingest via _run_local_parse_pipeline).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from vector_store import VectorStore
from index_registry import set_bm25_index, set_table_index, build_bm25_from_chunks, build_table_index_from_chunks
from doc_processor import Chunk

print("Loading existing chunks from vector store...")
vs = VectorStore()
chunk_count = vs.count()
print(f"  {chunk_count} chunks found")

# Get all chunks with full text
results = vs._collection.get(include=["documents", "metadatas"])
print(f"  Retrieved {len(results.get('ids', []))} entries")

# Build BM25
print("\nBuilding BM25 index...")
chunks_for_bm25 = []
for i, chunk_id in enumerate(results.get("ids", [])):
    text = results["documents"][i] if results.get("documents") else ""
    meta = results["metadatas"][i] if results.get("metadatas") else {}
    c = Chunk(
        chunk_id=chunk_id,
        text=text,
        content_type=meta.get("content_type", "text"),
        metadata=None,
    )
    chunks_for_bm25.append(c)

bm25 = build_bm25_from_chunks(chunks_for_bm25)
if bm25:
    set_bm25_index(bm25)
    print(f"  BM25 built with {len(chunks_for_bm25)} docs ✓")
else:
    print("  BM25 build failed ✗")

# Build TableIndex
print("\nBuilding TableIndex...")
table_chunks = [
    c for c in chunks_for_bm25
    if c.content_type == "table" or "<table>" in c.text.lower()
]
print(f"  Table-type chunks: {len(table_chunks)}")

ti = build_table_index_from_chunks(table_chunks if table_chunks else chunks_for_bm25)
if ti:
    set_table_index(ti)
    print(f"  TableIndex built with {ti.count()} rows ✓")
else:
    print("  TableIndex build failed ✗")

print("\nDone. Indices are now globally registered.")
