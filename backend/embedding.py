"""
Embedding Module — §2.2 of rag-engineering-blueprint-v1.0.

Converts chunk text to fixed-dimension semantic vectors using local
sentence-transformers models. No external API calls needed.

Default: BAAI/bge-small-zh-v1.5 (512-dim, Chinese+English, CPU-friendly)
Production: BAAI/bge-m3 (1024-dim, multilingual, GPU recommended)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from logging_config import get_logger

logger = get_logger(__name__)

# Set HuggingFace mirror BEFORE any sentence_transformers import.
# This must happen at module level so it's active when SentenceTransformer
# is first imported inside st_model property.
if not os.getenv("HF_ENDPOINT"):
    try:
        from dotenv import load_dotenv
        _env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(_env_path):
            load_dotenv(_env_path, override=True)
    except ImportError:
        pass
if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


# ── Constants ────────────────────────────────────────────────────────────────

MODEL_DIMENSIONS = {
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}

DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_DIM = MODEL_DIMENSIONS[DEFAULT_MODEL]
BATCH_SIZE = 32
CACHE_DIR = os.path.join(os.path.dirname(__file__), "output", "embedding_cache")
_st_model_cache: dict[str, object] = {}
_st_model_cache_lock = threading.Lock()
_cache_file_locks: dict[str, threading.Lock] = {}
_cache_file_locks_guard = threading.Lock()


# ── Embedding Client ─────────────────────────────────────────────────────────

class EmbeddingClient:
    """Local sentence-transformers embedding client with cache.

    Downloads the model on first use (~96MB for bge-small-zh-v1.5).
    All embedding happens locally — zero API cost, zero latency, data stays local.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        batch_size: int = BATCH_SIZE,
    ):
        self.model = model
        self.dim = MODEL_DIMENSIONS.get(model, 512)
        self.batch_size = batch_size
        self._st_model = None  # Lazy-loaded

        os.makedirs(CACHE_DIR, exist_ok=True)
        self._cache: dict[str, list[float]] = {}
        self._load_cache()

    @property
    def st_model(self):
        """Lazy-load the sentence-transformers model.

        HF_ENDPOINT is auto-configured at module level (default: https://hf-mirror.com).
        """
        if self._st_model is None:
            cached = _st_model_cache.get(self.model)
            if cached is not None:
                self._st_model = cached
                return self._st_model

            with _st_model_cache_lock:
                cached = _st_model_cache.get(self.model)
                if cached is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info("embedding_model_loading", model=self.model)
                    cached = SentenceTransformer(self.model)
                    logger.info("embedding_model_loaded", dim=self.dim)
                    _st_model_cache[self.model] = cached
                self._st_model = cached
        return self._st_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Cached results returned immediately.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of L2-normalized embedding vectors (same order as input).
        """
        vectors = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                vectors.append(self._cache[cache_key])
            else:
                vectors.append([])  # placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)

        if not uncached_texts:
            return vectors

        # Batch-encode uncached texts
        for batch_start in range(0, len(uncached_texts), self.batch_size):
            batch = uncached_texts[batch_start:batch_start + self.batch_size]
            batch_vectors = self._encode(batch)

            for j, vec in enumerate(batch_vectors):
                idx = uncached_indices[batch_start + j]
                text = uncached_texts[batch_start + j]
                vectors[idx] = vec
                self._cache[self._cache_key(text)] = vec

        self._save_cache()
        return vectors

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self.embed_texts([text])[0]

    def embed_query(self, query_text: str) -> list[float]:
        """Embed a query string. Uses same model as document embedding.

        Must use the SAME model as chunk embedding for vector space consistency.
        For BGE models, prepend 'query: ' prefix for better retrieval quality.
        """
        return self.embed_text(query_text)

    def embed_queries(self, query_texts: list[str]) -> list[list[float]]:
        """Embed multiple query variants (for Multi-Query recall)."""
        return self.embed_texts(query_texts)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts using the local model. Returns normalized vectors."""
        # BGE models benefit from instruction prefixes
        # For document chunks: no prefix needed
        # For queries: handled by embed_query caller
        embeddings = self.st_model.encode(
            texts,
            normalize_embeddings=True,  # L2 normalization built-in
            show_progress_bar=False,
            batch_size=self.batch_size,
        )
        return [e.tolist() for e in embeddings]

    def _cache_key(self, text: str) -> str:
        """Generate a cache key from text + model."""
        content = f"{self.model}:{text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def _load_cache(self):
        """Load persisted embedding cache."""
        safe_name = self.model.replace("/", "_").replace("-", "_")
        cache_path = os.path.join(CACHE_DIR, f"{safe_name}_cache.json")
        lock = _get_cache_file_lock(cache_path)
        with lock:
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._cache = {}

    def _save_cache(self):
        """Persist embedding cache to disk."""
        safe_name = self.model.replace("/", "_").replace("-", "_")
        cache_path = os.path.join(CACHE_DIR, f"{safe_name}_cache.json")
        lock = _get_cache_file_lock(cache_path)
        with lock:
            disk_cache = {}
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        disk_cache = json.load(f)
                except (json.JSONDecodeError, IOError):
                    disk_cache = {}

            disk_cache.update(self._cache)
            self._cache = disk_cache

            tmp_path = f"{cache_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
            try:
                os.replace(tmp_path, cache_path)
            except PermissionError:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False)
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except PermissionError:
                    pass

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self):
        """Clear embedding cache (e.g., after model migration)."""
        self._cache = {}
        safe_name = self.model.replace("/", "_").replace("-", "_")
        cache_path = os.path.join(CACHE_DIR, f"{safe_name}_cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)


# ── Factory ──────────────────────────────────────────────────────────────────

def create_embedding_client(model: str = DEFAULT_MODEL) -> EmbeddingClient:
    """Factory function for creating an EmbeddingClient."""
    return EmbeddingClient(model=model)


def _get_cache_file_lock(cache_path: str) -> threading.Lock:
    with _cache_file_locks_guard:
        lock = _cache_file_locks.get(cache_path)
        if lock is None:
            lock = threading.Lock()
            _cache_file_locks[cache_path] = lock
        return lock
