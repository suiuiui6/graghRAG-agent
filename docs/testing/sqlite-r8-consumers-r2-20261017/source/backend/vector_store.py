"""
Vector Database Module — §2.3 of rag-engineering-blueprint-v1.0.

ChromaDB-based vector store with HNSW indexing, metadata filtering,
and per-source document management. Supports incremental writes and
deletion by source file.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

# ChromaDB is optional at import time — installed on demand
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from doc_processor import Chunk


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_COLLECTION = "rag_docs"
DEFAULT_DIM = 512  # BAAI/bge-small-zh-v1.5
VECTORDB_DIR = os.path.join(os.path.dirname(__file__), "output", "vectordb")


# ── Vector Store ─────────────────────────────────────────────────────────────

class VectorStore:
    """ChromaDB-backed vector store for RAG document chunks.

    Usage:
        store = VectorStore()
        store.add_chunks(chunks, embeddings)
        results = store.search(query_vector, top_k=20, filter={"entity_types": "metric"})
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        persist_dir: str | None = None,
        embedding_dim: int = DEFAULT_DIM,
    ):
        if not HAS_CHROMADB:
            raise ImportError(
                "chromadb is required for VectorStore. Install: pip install chromadb"
            )

        self.collection_name = collection_name
        self.persist_dir = persist_dir or VECTORDB_DIR
        self.embedding_dim = embedding_dim

        os.makedirs(self.persist_dir, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception:  # noqa: BLE001  # Windows 文件锁容忍：目标被占用时跳过，不终止进程
            fallback_dir = _prepare_sqlite_safe_mirror(self.persist_dir)
            self.persist_dir = fallback_dir
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "dimension": embedding_dim},
        )

    # ── Write Operations ─────────────────────────────────────────────────

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ):
        """Add chunks with their embeddings to the vector store.

        Args:
            chunks: List of Chunk objects (must have chunk_id and metadata).
            embeddings: Corresponding embedding vectors (same length as chunks).
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Length mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings"
            )

        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [_build_chroma_metadata(c) for c in chunks]

        # ChromaDB doesn't support None in metadata — convert to ""
        for m in metadatas:
            for k, v in m.items():
                if v is None:
                    m[k] = ""

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def delete_by_source(self, source_file: str):
        """Delete all chunks from a specific source file.

        Useful for re-indexing a document.
        """
        results = self._collection.get(
            where={"source_file": source_file},
        )
        if results["ids"]:
            self._collection.delete(ids=results["ids"])

    def delete_by_chunk_ids(self, chunk_ids: list[str]):
        """Delete specific chunks by their IDs."""
        if chunk_ids:
            self._collection.delete(ids=chunk_ids)

    # ── Read / Search Operations ─────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        where: dict | None = None,
        text_char_limit: int | None = None,
        metadata_keys: list[str] | None = None,
    ) -> list[dict]:
        """Vector similarity search.

        Args:
            query_vector: Normalized query embedding vector.
            top_k: Number of results to return.
            where: Optional metadata filter dict (ChromaDB where syntax).
            text_char_limit: Optional character cap for returned text.
            metadata_keys: Optional whitelist of metadata fields to return.

        Returns:
            List of result dicts with keys: chunk_id, text, score, metadata.
        """
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                raw_metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                metadata = _parse_chroma_metadata(raw_metadata)
                if metadata_keys is not None:
                    metadata = {
                        key: metadata[key]
                        for key in metadata_keys
                        if key in metadata
                    }
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # Convert cosine distance → similarity score
                score = 1.0 - (distance / 2.0)  # ChromaDB cosine distance range [0, 2]
                text = results["documents"][0][i] if results["documents"] else ""
                if text_char_limit is not None:
                    text = text[:text_char_limit]

                output.append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "score": round(score, 4),
                    "source": "vector",
                    "metadata": metadata,
                })

        return output

    def get_by_ids(self, chunk_ids: list[str]) -> list[dict]:
        """Retrieve chunks by their IDs."""
        if not chunk_ids:
            return []

        results = self._collection.get(
            ids=chunk_ids,
            include=["documents", "metadatas"],
        )

        output = []
        for i, chunk_id in enumerate(results.get("ids", [])):
            output.append({
                "chunk_id": chunk_id,
                "text": results["documents"][i] if results.get("documents") else "",
                "metadata": _parse_chroma_metadata(
                    results["metadatas"][i] if results.get("metadatas") else {}
                ),
            })

        return output

    # ── Collection Management ────────────────────────────────────────────

    def count(self) -> int:
        """Return the number of chunks in the collection."""
        return self._collection.count()

    def list_sources(self) -> list[str]:
        """List all unique source files in the collection."""
        results = self._collection.get(include=["metadatas"])
        sources = set()
        if results.get("metadatas"):
            for m in results["metadatas"]:
                src = m.get("source_file", "")
                if src:
                    sources.add(src)
        return sorted(sources)

    def get_collection_info(self) -> dict:
        """Return collection metadata for health checks."""
        return {
            "name": self.collection_name,
            "count": self.count(),
            "dimension": self.embedding_dim,
            "sources": len(self.list_sources()),
            "persist_dir": self.persist_dir,
        }

    # ── Migration ────────────────────────────────────────────────────────

    def create_migration_collection(self, new_dim: int, suffix: str = "_v2") -> "VectorStore":
        """Create a new collection for model migration (different embedding dim).

        Uses the full VectorStore → ChromaDB → new collection path to avoid
        dimension mismatch on existing collection.
        """
        return VectorStore(
            collection_name=f"{self.collection_name}{suffix}",
            persist_dir=self.persist_dir,
            embedding_dim=new_dim,
        )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_chroma_metadata(chunk: Chunk) -> dict:
    """Convert Chunk metadata to ChromaDB-compatible flat dict.

    ChromaDB metadata must be str, int, float, or bool only.
    Lists and dicts are serialized to JSON strings.
    """
    if chunk.metadata is None:
        return {
            "source_file": "",
            "source_format": "",
            "content_type": chunk.content_type,
            "page_idx": 0,
        }

    meta = chunk.metadata
    entity_types_json = json.dumps(meta.entity_types) if meta.entity_types else "[]"
    section_path_json = json.dumps(meta.section_path) if meta.section_path else "[]"
    entity_ids_json = json.dumps(getattr(meta, "entity_ids", [])) if getattr(meta, "entity_ids", None) else "[]"

    return {
        "source_file": meta.source_file or "",
        "source_format": meta.source_format or "",
        "page_idx": meta.page_idx if meta.page_idx is not None else 0,
        "content_type": meta.content_type or chunk.content_type,
        "project_id": meta.project_id or "",
        "token_count": meta.token_count,
        "entity_types": entity_types_json,
        "section_path": section_path_json,
        "entity_ids": entity_ids_json,
        "char_start": meta.char_start,
        "char_end": meta.char_end,
    }


def _parse_chroma_metadata(meta: dict) -> dict:
    """Parse ChromaDB flat metadata back to structured dict."""
    if not meta:
        return {}

    result = dict(meta)

    # Deserialize JSON fields
    for field in ["entity_types", "section_path", "entity_ids"]:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                result[field] = []

    return result


# ── Factory ──────────────────────────────────────────────────────────────────

def create_vector_store(
    collection_name: str = DEFAULT_COLLECTION,
    embedding_dim: int = DEFAULT_DIM,
    persist_dir: str | None = None,
) -> VectorStore:
    """Factory function for creating a VectorStore instance."""
    return VectorStore(
        collection_name=collection_name,
        persist_dir=persist_dir or VECTORDB_DIR,
        embedding_dim=embedding_dim,
    )


def _prepare_sqlite_safe_mirror(source_dir: str) -> str:
    """Mirror the Chroma persist dir into a temp location that supports sqlite."""
    src = Path(source_dir)
    temp_root = Path(tempfile.gettempdir()) / "graphrag_chroma"
    mirror_dir = temp_root / src.name

    if mirror_dir.exists():
        shutil.rmtree(mirror_dir, ignore_errors=True)

    if src.exists() and any(src.iterdir()):
        shutil.copytree(src, mirror_dir, dirs_exist_ok=True)
    else:
        mirror_dir.mkdir(parents=True, exist_ok=True)

    return str(mirror_dir)
