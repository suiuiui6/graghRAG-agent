"""
Multi-turn Conversation Manager — §10.2 of enterprise-evolution-blueprint.

Session-based conversation storage with auto-TTL, coreference resolution
prompt builder, and JSON file persistence under output/conversations/.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import hashlib
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import requests

from logging_config import get_logger

logger = get_logger(__name__)

CONVERSATIONS_DIR = Path("output/conversations")
RUNTIME_CACHE_DB = Path("output/runtime_cache.sqlite3")
MAX_TURNS = 20
TTL_SECONDS = 30 * 60          # 30 min inactivity → inactive
RETENTION_DAYS = 7             # Auto-delete after 7 days
_runtime_cache_lock = threading.Lock()
_runtime_cache_ready = False
_AUTO_SESSION_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def _ensure_runtime_cache() -> None:
    global _runtime_cache_ready
    if _runtime_cache_ready:
        return

    with _runtime_cache_lock:
        if _runtime_cache_ready:
            return
        RUNTIME_CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(RUNTIME_CACHE_DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
        _runtime_cache_ready = True


def _hash_cache_payload(payload) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _should_preserve_requested_session_id(session_id: str | None) -> bool:
    if not session_id:
        return False
    # Preserve caller-owned stable IDs (for evals or external clients) but
    # rotate auto-generated runtime IDs when an old conversation has expired.
    return _AUTO_SESSION_ID_RE.fullmatch(session_id) is None


def runtime_cache_get(namespace: str, payload) -> str | None:
    _ensure_runtime_cache()
    cache_key = _hash_cache_payload(payload)
    with sqlite3.connect(RUNTIME_CACHE_DB) as conn:
        row = conn.execute(
            "SELECT value FROM runtime_cache WHERE namespace = ? AND cache_key = ?",
            (namespace, cache_key),
        ).fetchone()
    return row[0] if row else None


def runtime_cache_put(namespace: str, payload, value: str) -> None:
    _ensure_runtime_cache()
    cache_key = _hash_cache_payload(payload)
    with sqlite3.connect(RUNTIME_CACHE_DB) as conn:
        conn.execute(
            """
            INSERT INTO runtime_cache (namespace, cache_key, value, created_at)
            VALUES (?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(namespace, cache_key)
            DO UPDATE SET value = excluded.value, created_at = excluded.created_at
            """,
            (namespace, cache_key, value),
        )
        conn.commit()


# ── data models (lightweight, no pydantic to avoid circular imports) ─────


class Turn:
    def __init__(self, turn_id: int, question: str, answer: str = "",
                 rewritten: str | None = None, rewrite_reason: str | None = None,
                 sources: list[str] | None = None):
        self.turn_id = turn_id
        self.question = question
        self.rewritten = rewritten
        self.rewrite_reason = rewrite_reason
        self.answer = answer
        self.sources = sources or []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "question": self.question,
            "rewritten_query": self.rewritten,
            "rewrite_reason": self.rewrite_reason,
            "answer": self.answer,
            "sources": self.sources,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        t = cls(d["turn_id"], d.get("question", ""))
        t.rewritten = d.get("rewritten_query")
        t.rewrite_reason = d.get("rewrite_reason")
        t.answer = d.get("answer", "")
        t.sources = d.get("sources", [])
        t.created_at = d.get("created_at", "")
        return t


class Conversation:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid4().hex[:12]
        self.title = ""
        self.turns: list[Turn] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_active = self.created_at
        self.user_id: str | None = None
        self.is_active = True

    def add_turn(self, question: str, answer: str = "",
                 rewritten: str | None = None, rewrite_reason: str | None = None,
                 sources: list[str] | None = None):
        if len(self.turns) >= MAX_TURNS:
            self.turns = self.turns[-(MAX_TURNS - 1):]
        turn_id = self.turns[-1].turn_id + 1 if self.turns else 1
        if not self.title and question:
            self.title = question[:60] + ("..." if len(question) > 60 else "")
        self.turns.append(Turn(turn_id, question, answer, rewritten, rewrite_reason, sources))
        self.last_active = datetime.now(timezone.utc).isoformat()
        self.is_active = True

    def recent_history(self, n: int = 3) -> list[dict]:
        """Return last N turns as chat history for prompt injection."""
        recent = [
            turn for turn in self.turns[-n:]
            if turn.question and turn.answer
        ]
        return [
            {"role": "user", "content": t.question,
             "answer": t.answer[:300] if t.answer else "",
             "sources": t.sources}
            for t in recent
        ]

    def expired(self) -> bool:
        try:
            last = datetime.fromisoformat(self.last_active)
            return (datetime.now(timezone.utc) - last).total_seconds() > TTL_SECONDS
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "turns": [t.to_dict() for t in self.turns],
            "created_at": self.created_at,
            "last_active": self.last_active,
            "user_id": self.user_id,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Conversation":
        c = cls(d.get("session_id", ""))
        c.title = d.get("title", "")
        c.turns = [Turn.from_dict(t) for t in d.get("turns", [])]
        c.created_at = d.get("created_at", c.created_at)
        c.last_active = d.get("last_active", c.last_active)
        c.user_id = d.get("user_id")
        c.is_active = d.get("is_active", True)
        return c


# ── manager ───────────────────────────────────────────────────────────────


class ConversationManager:
    """File-based conversation persistence with auto-cleanup."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or CONVERSATIONS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._session_locks: dict[str, threading.Lock] = {}
        self._session_locks_guard = threading.Lock()

    def _path(self, session_id: str) -> Path:
        # Sanitize to prevent path traversal
        safe = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)
        return self.base_dir / f"{safe}.json"

    def _session_lock(self, session_id: str) -> threading.Lock:
        with self._session_locks_guard:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    def create(self, question: str = "", session_id: str | None = None) -> Conversation:
        conv = Conversation(session_id=session_id)
        if question:
            conv.title = question[:60] + ("..." if len(question) > 60 else "")
        self._save(conv)
        logger.info("conversation_created", session_id=conv.session_id)
        return conv

    def get_or_create(self, session_id: str | None, question: str = "") -> Conversation:
        if session_id:
            conv = self.load(session_id)
            if conv and conv.is_active and not conv.expired():
                return conv
            if conv is not None:
                if _should_preserve_requested_session_id(session_id):
                    return self.create(question, session_id=session_id)
                return self.create(question)
        return self.create(question, session_id=session_id)

    def load(self, session_id: str) -> Conversation | None:
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            conv = Conversation.from_dict(data)
            if conv.expired():
                conv.is_active = False
                self._save(conv)
                logger.info("conversation_expired", session_id=session_id)
            return conv
        except Exception as e:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            logger.warning("conversation_load_error", session_id=session_id, error=str(e))
            return None

    def _save(self, conv: Conversation) -> None:
        p = self._path(conv.session_id)
        tmp_path = p.with_suffix(".json.tmp")
        payload = json.dumps(conv.to_dict(), ensure_ascii=False, indent=2)
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, p)
        except PermissionError:
            p.write_text(payload, encoding="utf-8")
            try:
                tmp_path.unlink(missing_ok=True)
            except PermissionError:
                logger.warning("conversation_tmp_cleanup_failed", path=str(tmp_path))

    def append_turn(self, session_id: str, question: str, answer: str = "",
                    rewritten: str | None = None, rewrite_reason: str | None = None,
                    sources: list[str] | None = None) -> Conversation | None:
        with self._session_lock(session_id):
            conv = self.load(session_id)
            if conv is None:
                return None
            conv.add_turn(question, answer, rewritten, rewrite_reason, sources)
            self._save(conv)
            return conv

    def list_all(self, include_inactive: bool = False, limit: int = 50) -> list[dict]:
        result = []
        for f in sorted(self.base_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not include_inactive and not data.get("is_active", True):
                    continue
                result.append({
                    "session_id": data.get("session_id"),
                    "title": data.get("title", ""),
                    "turns": len(data.get("turns", [])),
                    "created_at": data.get("created_at", ""),
                    "last_active": data.get("last_active", ""),
                    "is_active": data.get("is_active", True),
                })
                if len(result) >= limit:
                    break
            except Exception:  # noqa: S110, BLE001  # 缓存读写失败可容忍：命中率下降但结果正确
                pass
        return result

    def delete(self, session_id: str) -> bool:
        p = self._path(session_id)
        if p.exists():
            p.unlink()
            logger.info("conversation_deleted", session_id=session_id)
            return True
        return False

    def cleanup(self, retention_days: int = RETENTION_DAYS) -> int:
        """Delete inactive conversations older than retention_days. Returns count removed."""
        cutoff = time.time() - retention_days * 86400
        removed = 0
        for f in self.base_dir.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if not data.get("is_active", True):
                        f.unlink()
                        removed += 1
                except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
                    pass
        if removed > 0:
            logger.info("conversation_cleanup", removed=removed)
        return removed

    def export_markdown(self, session_id: str) -> str | None:
        """Export conversation as markdown."""
        conv = self.load(session_id)
        if conv is None:
            return None
        lines = [f"# {conv.title or '对话记录'}", "",
                 f"会话ID: {conv.session_id} | 创建: {conv.created_at[:16]} | 共 {len(conv.turns)} 轮", ""]
        for t in conv.turns:
            lines.append(f"## 第 {t.turn_id} 轮")
            lines.append(f"**问**: {t.question}")
            if t.rewritten and t.rewritten != t.question:
                lines.append(f"*(改写: {t.rewritten})*")
            if t.rewrite_reason:
                lines.append(f"*(改写原因: {t.rewrite_reason})*")
            lines.append(f"**答**: {t.answer}")
            if t.sources:
                lines.append(f"*来源: {', '.join(t.sources[:5])}*")
            lines.append("")
        return "\n".join(lines)


# ── coreference resolution prompt ─────────────────────────────────────────


COREFERENCE_PROMPT = """\
You are a query rewriter. Given the conversation history and the user's latest question,
rewrite the question to be SELF-CONTAINED and UNAMBIGUOUS.

Rules:
- Resolve pronouns (它, 这个, 那, 这些) to the specific entities/concepts they refer to.
- Resolve ordinal references (第一条, 第二个, 上述) to the specific items.
- If the question is already self-contained, return it as-is.
- Do NOT answer the question, only rewrite it.

Conversation history:
{history}

Latest question: {question}

Rewritten question (output ONLY the rewritten question, no explanation):"""


def resolve_coreference(
    question: str,
    history: list[dict],
    model: str = "deepseek-chat",
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """Use LLM to resolve coreferences in a follow-up question.

    Args:
        question: The latest user question.
        history: List of {role, content, answer?, sources?} dicts.
        model: LLM model name.
        api_key: API key (defaults to env LANGEXTRACT_API_KEY).
        base_url: API base URL (defaults to env LANGEXTRACT_BASE_URL).

    Returns:
        Rewritten self-contained question, or original question on failure.
    """
    if not history:
        return question

    # Build history summary
    history_lines = []
    for i, turn in enumerate(history[-3:], 1):
        q = turn.get("content", "")[:200]
        a = turn.get("answer", "")[:200]
        history_lines.append(f"Turn {i}: Q: {q}\nA: {a}")
    history_text = "\n".join(history_lines)

    prompt = COREFERENCE_PROMPT.format(history=history_text, question=question)
    cache_payload = {
        "question": question,
        "history": history[-3:],
        "model": model,
        "base_url": base_url or os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
    }

    try:
        cached = runtime_cache_get("coreference_resolution", cache_payload)
        if cached:
            return cached
    except Exception:  # noqa: BLE001  # 缓存读写失败可容忍：命中率下降但结果正确
        logger.warning("coreference_cache_read_failed", exc_info=True)

    try:
        api_key = api_key or os.getenv("LANGEXTRACT_API_KEY", "")
        base_url = base_url or os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com")

        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 200,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        rewritten = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip quotes if LLM wraps it
        rewritten = rewritten.strip('"').strip("'").strip()
        if not rewritten or len(rewritten) < 2:
            return question
        try:
            runtime_cache_put("coreference_resolution", cache_payload, rewritten)
        except Exception:  # noqa: BLE001  # 缓存读写失败可容忍：命中率下降但结果正确
            logger.warning("coreference_cache_write_failed", exc_info=True)
        logger.info("coreference_resolved", original=question[:60], rewritten=rewritten[:60])
        return rewritten
    except Exception as e:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        logger.warning("coreference_failed", error=str(e)[:100])
        return question


# ── singleton ─────────────────────────────────────────────────────────────

_mgr: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    global _mgr
    if _mgr is None:
        _mgr = ConversationManager()
    return _mgr
