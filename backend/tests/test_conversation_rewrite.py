from tests.request_helpers import admin_request
import asyncio
from pathlib import Path

from models import QueryOptions, QueryRequest
import conversation as conversation_module
import routes.conversation as conversation_route_module
import routes.rag_query as rag_query_module


class InMemoryConversationManager(conversation_module.ConversationManager):
    def __init__(self):
        self._store: dict[str, conversation_module.Conversation] = {}
        self._session_locks = {}
        self._session_locks_guard = conversation_module.threading.Lock()
        self.base_dir = Path(".")

    def create(self, question: str = "", session_id: str | None = None) -> conversation_module.Conversation:
        conv = conversation_module.Conversation(session_id=session_id)
        if question:
            conv.title = question[:60] + ("..." if len(question) > 60 else "")
        self._store[conv.session_id] = conv
        return conv

    def load(self, session_id: str) -> conversation_module.Conversation | None:
        return self._store.get(session_id)

    def _save(self, conv: conversation_module.Conversation) -> None:
        self._store[conv.session_id] = conv

    def delete(self, session_id: str) -> bool:
        return self._store.pop(session_id, None) is not None


def test_followup_question_persists_rewritten_query_and_reason(monkeypatch):
    manager = InMemoryConversationManager()

    class DummyPipeline:
        pass

    class DummyGenerator:
        def __init__(self, retrieval_pipeline, config=None):
            self.retrieval_pipeline = retrieval_pipeline
            self.config = config

        def generate(
            self,
            query,
            chat_history=None,
            max_context_tokens=12000,
            retrieval_config=None,
        ):
            return {
                "answer": f"answer:{query}",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": False,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            }

    monkeypatch.setattr(conversation_module, "get_conversation_manager", lambda: manager)
    monkeypatch.setattr(
        conversation_module,
        "resolve_coreference",
        lambda question, history, **kwargs: "W4S1 对应的弃电量是多少？"
        if question == "它对应的弃电量是多少？"
        else question,
    )
    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    session_id = "session-rewrite-1"
    asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(
                query="W4S1 是什么？",
                session_id=session_id,
                options=QueryOptions(include_sources=True),
            ),
            request=admin_request(),
        )
    )
    followup_response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(
                query="它对应的弃电量是多少？",
                session_id=session_id,
                options=QueryOptions(include_sources=True),
            ),
            request=admin_request(),
        )
    )

    assert followup_response.metadata["rewritten_query"] == "W4S1 对应的弃电量是多少？"
    assert followup_response.metadata["rewrite_reason"] == "coreference_resolution"


def test_conversation_detail_exposes_rewrite_diagnostics(monkeypatch):
    manager = InMemoryConversationManager()

    class DummyPipeline:
        pass

    class DummyGenerator:
        def __init__(self, retrieval_pipeline, config=None):
            self.retrieval_pipeline = retrieval_pipeline
            self.config = config

        def generate(
            self,
            query,
            chat_history=None,
            max_context_tokens=12000,
            retrieval_config=None,
        ):
            return {
                "answer": f"answer:{query}",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": False,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            }

    monkeypatch.setattr(conversation_module, "get_conversation_manager", lambda: manager)
    monkeypatch.setattr(conversation_route_module, "get_conversation_manager", lambda: manager)
    monkeypatch.setattr(
        conversation_module,
        "resolve_coreference",
        lambda question, history, **kwargs: "W4S1 对应的弃电量是多少？"
        if question == "它对应的弃电量是多少？"
        else question,
    )
    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    session_id = "session-rewrite-2"
    asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(
                query="W4S1 是什么？",
                session_id=session_id,
                options=QueryOptions(include_sources=True),
            ),
            request=admin_request(),
        )
    )
    asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(
                query="它对应的弃电量是多少？",
                session_id=session_id,
                options=QueryOptions(include_sources=True),
            ),
            request=admin_request(),
        )
    )

    detail = asyncio.run(conversation_route_module.get_conversation(session_id))

    assert detail["turns"][1]["rewritten_query"] == "W4S1 对应的弃电量是多少？"
    assert detail["turns"][1]["rewrite_reason"] == "coreference_resolution"


def test_save_fallback_tolerates_tmp_cleanup_permission_error(monkeypatch):
    store: dict[str, str] = {}

    def fake_mkdir(self, parents=False, exist_ok=False):
        return None

    def fake_write_text(self, data, encoding=None):
        store[str(self)] = data
        return len(data)

    def fake_read_text(self, encoding=None):
        return store[str(self)]

    def fake_exists(self):
        return str(self) in store

    def fake_unlink(self, missing_ok=False):
        if self.name.endswith(".json.tmp"):
            raise PermissionError("cleanup denied")
        if missing_ok:
            store.pop(str(self), None)
            return None
        del store[str(self)]
        return None

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    monkeypatch.setattr(Path, "write_text", fake_write_text)
    monkeypatch.setattr(Path, "read_text", fake_read_text)
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    manager = conversation_module.ConversationManager(base_dir=Path("D:/virtual/test-conversations/perm-fallback"))
    conv = conversation_module.Conversation(session_id="perm-fallback")
    conv.add_turn("Q1", "A1")

    monkeypatch.setattr(conversation_module.os, "replace", lambda src, dst: (_ for _ in ()).throw(PermissionError("replace denied")))

    manager._save(conv)

    saved = manager.load("perm-fallback")
    assert saved is not None
    assert saved.turns[0].question == "Q1"


def test_recent_history_excludes_turns_without_answer_text():
    conv = conversation_module.Conversation(session_id="history-filter")
    conv.add_turn("Q1", "A1")
    conv.add_turn("Q2", "")
    conv.add_turn("Q3", "A3")
    conv.add_turn("Q4", "A4")

    history = conv.recent_history(3)

    assert [turn["content"] for turn in history] == ["Q3", "Q4"]
    assert [turn["answer"] for turn in history] == ["A3", "A4"]


def test_get_or_create_reuses_requested_session_id_after_expired_conversation():
    manager = InMemoryConversationManager()
    expired = conversation_module.Conversation(session_id="mt-session-w2s2")
    expired.add_turn("旧问题", "旧回答")
    expired.is_active = False
    expired.last_active = "2025-01-01T00:00:00+00:00"
    manager._save(expired)

    fresh = manager.get_or_create("mt-session-w2s2", "论文中提到的 W2S2 场景是什么？")

    assert fresh.session_id == "mt-session-w2s2"
    assert fresh.turns == []
    assert fresh.is_active is True
