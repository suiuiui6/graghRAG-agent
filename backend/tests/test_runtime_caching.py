import importlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


class InMemoryKVCache:
    def __init__(self):
        self.store = {}

    def get(self, cache_key: str):
        return self.store.get(cache_key)

    def set(self, cache_key: str, payload: dict) -> None:
        self.store[cache_key] = payload


class InMemoryConversationManager:
    def __init__(self):
        self._store = {}
        self._session_locks = {}
        self._session_locks_guard = __import__("threading").Lock()
        self.base_dir = Path(".")

    def create(self, question: str = "", session_id: str | None = None):
        import conversation

        conv = conversation.Conversation(session_id=session_id)
        if question:
            conv.title = question[:60] + ("..." if len(question) > 60 else "")
        self._store[conv.session_id] = conv
        return conv

    def get_or_create(self, session_id: str | None, question: str = ""):
        import conversation

        return conversation.ConversationManager.get_or_create(self, session_id, question)

    def load(self, session_id: str):
        return self._store.get(session_id)

    def _save(self, conv) -> None:
        self._store[conv.session_id] = conv


def test_cross_encoder_is_cached_process_wide(monkeypatch):
    import retrieval

    retrieval = importlib.reload(retrieval)
    init_calls = []

    class DummyCrossEncoder:
        def __init__(self, model_name, max_length=512):
            init_calls.append((model_name, max_length))

        def predict(self, pairs):
            return [0.9 for _ in pairs]

    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", type(
        "SentenceTransformersModule",
        (),
        {"CrossEncoder": DummyCrossEncoder},
    )())

    first = retrieval.get_cross_encoder()
    second = retrieval.get_cross_encoder()

    assert init_calls == [("BAAI/bge-reranker-base", 512)]
    assert first is second


def test_query_rewrite_cache_reuses_prior_result(monkeypatch):
    import retrieval

    retrieval = importlib.reload(retrieval)
    cache = InMemoryKVCache()
    cache.set("q:预算执行率", {"rewritten": "预算执行率", "intent": "metric"})

    assert cache.get("q:预算执行率")["intent"] == "metric"


def test_embedding_model_is_cached_process_wide(monkeypatch):
    import embedding

    embedding = importlib.reload(embedding)
    init_calls = []

    class DummySentenceTransformer:
        def __init__(self, model_name):
            init_calls.append(model_name)

        def encode(self, texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32):
            return [SimpleNamespace(tolist=lambda: [0.1, 0.2]) for _ in texts]

    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", type(
        "SentenceTransformersModule",
        (),
        {"SentenceTransformer": DummySentenceTransformer},
    )())

    first = embedding.EmbeddingClient()
    second = embedding.EmbeddingClient()

    assert first.st_model is second.st_model
    assert init_calls == [embedding.DEFAULT_MODEL]


def test_preprocess_query_uses_sqlite_cache_before_second_llm_call(monkeypatch):
    import retrieval

    retrieval = importlib.reload(retrieval)

    cache = InMemoryKVCache()
    monkeypatch.setattr(retrieval, "get_query_rewrite_cache", lambda path=None: cache)

    post_calls = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"rewritten":"rewritten query","intent":"metric",'
                                '"entity_types":["metric"],"table_conditions":[]}'
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        post_calls.append((args, kwargs))
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)

    first = retrieval.preprocess_query("raw query")
    second = retrieval.preprocess_query("raw query")

    assert first.rewritten == "rewritten query"
    assert second.rewritten == "rewritten query"
    assert len(post_calls) == 1


def test_resolve_coreference_uses_sqlite_cache_before_second_llm_call(monkeypatch):
    import conversation

    conversation = importlib.reload(conversation)
    cache = {}

    post_calls = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "企业级演进蓝图中的协作闭环方案是什么？"
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        post_calls.append((args, kwargs))
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr(
        conversation,
        "runtime_cache_get",
        lambda namespace, payload: cache.get((namespace, conversation._hash_cache_payload(payload))),
    )
    monkeypatch.setattr(
        conversation,
        "runtime_cache_put",
        lambda namespace, payload, value: cache.__setitem__(
            (namespace, conversation._hash_cache_payload(payload)),
            value,
        ),
    )

    history = [
        {
            "role": "user",
            "content": "企业级演进蓝图里有哪些部分？",
            "answer": "包括协作闭环、数据资产、生态集成。",
        }
    ]

    first = conversation.resolve_coreference("其中协作闭环方案是什么？", history)
    second = conversation.resolve_coreference("其中协作闭环方案是什么？", history)

    assert first == "企业级演进蓝图中的协作闭环方案是什么？"
    assert second == first
    assert len(post_calls) == 1


def test_get_or_create_returns_new_session_when_existing_conversation_expired():
    import conversation

    conversation = importlib.reload(conversation)
    manager = InMemoryConversationManager()
    first = manager.create("first question")

    expired = manager.load(first.session_id)
    expired.last_active = (datetime.now(timezone.utc) - timedelta(seconds=conversation.TTL_SECONDS + 10)).isoformat()
    manager._save(expired)

    second = manager.get_or_create(first.session_id, "second question")

    assert second.session_id != first.session_id


def test_rag_pipeline_init_happens_once_without_false_fallback(monkeypatch):
    import routes.rag_query as rag_query
    import embedding
    import vector_store
    import retrieval
    import routes.query
    import index_registry
    import domain_dict
    import time

    rag_query = importlib.reload(rag_query)
    init_calls = {"embedding": 0, "pipeline": 0}

    class DummyEmbeddingClient:
        def __init__(self):
            init_calls["embedding"] += 1
            time.sleep(0.1)

    class DummyVectorStore:
        def __init__(self):
            pass

    class DummyPipeline:
        def __init__(self, **kwargs):
            init_calls["pipeline"] += 1

    monkeypatch.setattr(embedding, "EmbeddingClient", DummyEmbeddingClient)
    monkeypatch.setattr(vector_store, "VectorStore", DummyVectorStore)
    monkeypatch.setattr(retrieval, "RetrievalPipeline", DummyPipeline)
    monkeypatch.setattr(routes.query, "_build_kg", lambda: None)
    monkeypatch.setattr(index_registry, "get_bm25_index", lambda: None)
    monkeypatch.setattr(index_registry, "get_table_index", lambda: None)
    monkeypatch.setattr(domain_dict, "get_domain_dict", lambda: None)

    rag_query._rag_pipeline = None
    rag_query._embedding_client = None
    rag_query._vector_store = None
    rag_query._init_failed = False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: rag_query._init_rag_pipeline(), range(2)))

    assert results == [True, True]
    assert init_calls["embedding"] == 1
    assert init_calls["pipeline"] == 1
    assert rag_query._rag_pipeline is not None


def test_warm_rag_runtime_primes_embedding_and_cross_encoder(monkeypatch):
    import routes.rag_query as rag_query

    rag_query._rag_pipeline = SimpleNamespace(config=SimpleNamespace(enable_cross_encoder=True))

    class DummyEmbeddingClient:
        def __init__(self):
            self.calls = []

        def embed_text(self, text):
            self.calls.append(text)
            return [0.1, 0.2]

    embedding_client = DummyEmbeddingClient()
    rag_query._embedding_client = embedding_client
    rag_query._vector_store = object()
    rag_query._init_failed = False

    cross_calls = []

    monkeypatch.setattr(rag_query, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("retrieval.get_cross_encoder", lambda: cross_calls.append("warm") or object())

    assert rag_query.warm_rag_runtime() is True
    assert embedding_client.calls == ["warmup"]
    assert cross_calls == ["warm"]


def test_invalidate_rag_runtime_clears_cached_singletons():
    import routes.rag_query as rag_query

    rag_query._rag_pipeline = object()
    rag_query._embedding_client = object()
    rag_query._vector_store = object()
    rag_query._init_failed = True

    rag_query.invalidate_rag_runtime()

    assert rag_query._rag_pipeline is None
    assert rag_query._embedding_client is None
    assert rag_query._vector_store is None
    assert rag_query._init_failed is False


def test_reload_kg_invalidates_rag_runtime(monkeypatch):
    import routes.query as query_route
    import routes.rag_query as rag_query

    query_route.G_grounded = object()
    query_route._agent = object()
    rag_query._rag_pipeline = object()
    rag_query._embedding_client = object()
    rag_query._vector_store = object()
    rag_query._init_failed = True

    monkeypatch.setattr(query_route, "_build_kg", lambda: "fresh-kg")
    monkeypatch.setattr(query_route, "_build_agent", lambda g: {"graph": g})

    query_route.reload_kg()

    assert query_route.G_grounded == "fresh-kg"
    assert query_route._agent == {"graph": "fresh-kg"}
    assert rag_query._rag_pipeline is None
    assert rag_query._embedding_client is None
    assert rag_query._vector_store is None
    assert rag_query._init_failed is False
