"""
Feishu (Lark) Client — §6.2 of enterprise-evolution-blueprint.

SDK wrapper for tenant_access_token management, message sending, and
event signature verification. Uses Feishu OpenAPI v3.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import requests

from logging_config import get_logger

logger = get_logger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """Feishu OpenAPI client for bot integration."""

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self.encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

        self._tenant_token: str | None = None
        self._token_expires_at: float = 0

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    # ── Token ──────────────────────────────────────────────────────────

    def _get_tenant_token(self) -> str:
        now = time.time()
        if self._tenant_token and now < self._token_expires_at - 60:
            return self._tenant_token

        resp = requests.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._tenant_token = data["tenant_access_token"]
        self._token_expires_at = now + data.get("expire", 7200)
        logger.info("feishu_token_refreshed")
        return self._tenant_token

    # ── Signature Verification ─────────────────────────────────────────

    def verify_signature(self, timestamp: str, nonce: str,
                         body: bytes, signature: str) -> bool:
        """Verify Feishu event signature (X-Lark-Signature)."""
        if not self.encrypt_key:
            logger.warning("feishu_encrypt_key_not_set")
            return False
        raw = f"{timestamp}{nonce}{self.encrypt_key}".encode("utf-8") + body
        expected = hashlib.sha256(raw).hexdigest()
        return hmac.compare_digest(signature.encode("utf-8"), expected.encode("ascii"))

    # ── Message ────────────────────────────────────────────────────────

    def send_message(self, receive_id: str, msg_type: str,
                     content: str, receive_id_type: str = "chat_id") -> dict:
        """Send a message via Feishu API."""
        token = self._get_tenant_token()
        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        resp = requests.post(
            f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={receive_id_type}",
            json=body,
            headers={"Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("feishu_message_sent", message_id=result.get("data", {}).get("message_id"))
        return result

    def reply_card(self, chat_id: str, card_json: dict) -> dict:
        """Reply with an interactive card in a chat."""
        content = json.dumps(card_json, ensure_ascii=False)
        return self.send_message(chat_id, "interactive", content)

    def reply_text(self, chat_id: str, text: str) -> dict:
        """Reply with plain text."""
        content = json.dumps({"text": text}, ensure_ascii=False)
        return self.send_message(chat_id, "text", content)

    # ── Card Builder ───────────────────────────────────────────────────

    def build_qa_card(self, question: str, answer: str, sources: list[str],
                      query_id: str = "", base_url: str = "") -> dict:
        """Build a Q&A interactive card with feedback buttons."""
        source_text = "\n".join([f"📄 {s}" for s in sources[:3]])
        if len(sources) > 3:
            source_text += f"\n... 共 {len(sources)} 条来源"

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 {question[:40]}{'...' if len(question) > 40 else ''}"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"{answer}\n\n---\n{source_text}",
                },
                {
                    "tag": "action",
                    "actions": [
                        {"tag": "button", "text": {"tag": "plain_text", "content": "👍"}, "value": f"positive|{query_id}"},
                        {"tag": "button", "text": {"tag": "plain_text", "content": "👎"}, "value": f"negative|{query_id}"},
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "由 GraphRAG 知识引擎驱动 · 如有误请反馈"}],
                },
            ],
        }
        return card

    def build_error_card(self, message: str = "抱歉，查询失败，请稍后重试。") -> dict:
        """Build a generic error card."""
        return {
            "header": {"title": {"tag": "plain_text", "content": "⚠ 查询失败"}, "template": "red"},
            "elements": [
                {"tag": "markdown", "content": message},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "GraphRAG Bot"}]},
            ],
        }
