"""
Bot Handler — §6.2 of enterprise-evolution-blueprint.

Message routing: extract @mention text → RAG query → format card reply.
Handles Feishu event callbacks and feedback button actions.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from logging_config import get_logger

logger = get_logger(__name__)


class BotHandler:
    """Routes bot events to the RAG pipeline and formats replies."""

    def __init__(self):
        self._daily_queries: dict[str, int] = {}  # user_id → count

    # ── Event Router ───────────────────────────────────────────────────

    def handle_event(self, event_type: str, event_data: dict) -> dict | None:
        """Route Feishu event to appropriate handler. Returns reply card or None."""
        if event_type == "url_verification":
            return {"challenge": event_data.get("challenge", "")}

        if event_type == "im.message.receive_v1":
            return self._handle_message(event_data)

        # Card button click (👍/👎 feedback from interactive cards)
        if event_type == "card.action.trigger":
            return self._handle_card_action(event_data)

        # Legacy: direct message reaction
        if event_type == "im.message.reaction.created":
            return self._handle_reaction(event_data)

        logger.debug("unhandled_event_type", event_type=event_type)
        return None

    # ── Card Action Handler ─────────────────────────────────────────────

    def _handle_card_action(self, event_data: dict) -> dict | None:
        """Handle interactive card button clicks (card.action.trigger)."""
        action = event_data.get("action", {})
        value = action.get("value", "")  # "positive|query_id" or "negative|query_id"
        open_id = event_data.get("open_id", "")

        parts = value.split("|")
        if len(parts) < 2:
            return None
        rating, query_id = parts[0], parts[1]

        # Submit feedback via Phase 1 feedback system
        try:
            from services.feedback_store import get_feedback_store
            fb = get_feedback_store()
            from models import FeedbackCreate
            fb.submit(FeedbackCreate(
                query_id=query_id,
                rating=rating,
                comment=f"来自飞书卡片 — {open_id}",
            ))
            logger.info("bot_card_feedback_recorded", rating=rating, query_id=query_id)
        except Exception as e:  # noqa: BLE001  # 卡片反馈落盘失败仅记录错误，不影响卡片交互响应
            logger.error("bot_card_feedback_failed", error=str(e))

        # Return a toast message to the user
        return {"toast": {"type": "success", "content": "感谢反馈！" if rating == "positive" else "感谢反馈，我们会改进！"}}

    # ── Message Handler ────────────────────────────────────────────────

    def _handle_message(self, event_data: dict) -> dict | None:
        message = event_data.get("message", {})
        sender = event_data.get("sender", {}).get("sender_id", {})
        sender_id = sender.get("open_id", "") if isinstance(sender, dict) else ""
        chat_id = message.get("chat_id", "")
        msg_type = message.get("msg_type", "")

        # Extract text from message
        text = ""
        if msg_type == "text":
            text = json.loads(message.get("content", "{}")).get("text", "")
        elif msg_type == "post":
            # Rich text — extract first paragraph
            content = json.loads(message.get("content", "{}"))
            for para in content.get("content", [[]])[0] if content.get("content") else []:
                if isinstance(para, list):
                    for seg in para:
                        if isinstance(seg, dict) and seg.get("tag") == "text":
                            text += seg.get("text", "")
                elif isinstance(para, dict) and para.get("tag") == "text":
                    text += para.get("text", "")

        if not text.strip():
            return None

        # Strip @mention
        text = re.sub(r'@\S+\s*', '', text).strip()
        if not text:
            return None

        # Rate limit check
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"{sender_id}:{today}"
        count = self._daily_queries.get(key, 0)
        if count > int(os.getenv("BOT_DAILY_LIMIT", "500")):
            from services.feishu_client import FeishuClient
            client = FeishuClient()
            if client.configured:
                client.reply_text(chat_id, "今日查询次数已达上限，请明天再试。")
            return None
        self._daily_queries[key] = count + 1

        # Call RAG pipeline
        try:
            answer, sources = self._rag_query(text)
        except Exception as e:  # noqa: BLE001  # Bot 内 RAG 查询失败仅记录错误并回复兜底文案，不中断消息处理
            logger.error("bot_rag_query_failed", error=str(e))
            from services.feishu_client import FeishuClient
            client = FeishuClient()
            if client.configured:
                card = client.build_error_card()
                client.reply_card(chat_id, card)
            return None

        # Build and send card
        from services.feishu_client import FeishuClient
        client = FeishuClient()
        if client.configured:
            card = client.build_qa_card(text, answer, sources, query_id="",
                                       base_url=os.getenv("FRONTEND_URL", ""))
            try:
                client.reply_card(chat_id, card)
            except Exception as e:  # noqa: BLE001  # 飞书卡片回复失败仅记录错误，不阻断 Bot 消息处理
                logger.error("feishu_reply_failed", error=str(e))

        logger.info("bot_query_handled", sender=sender_id, text=text[:80])
        return None  # Reply sent via API, not as callback response

    # ── Reaction Handler ───────────────────────────────────────────────

    def _handle_reaction(self, event_data: dict) -> dict | None:
        """Handle 👍/👎 reaction as feedback."""
        action = event_data.get("action", {})
        value = action.get("value", "")  # "positive|query_id" or "negative|query_id"
        sender = event_data.get("sender", {}).get("sender_id", {})
        sender_id = sender.get("open_id", "") if isinstance(sender, dict) else ""

        parts = value.split("|")
        if len(parts) < 2:
            return None
        rating, query_id = parts[0], parts[1]

        # Submit feedback via Phase 1 feedback system
        try:
            from services.feedback_store import get_feedback_store
            fb = get_feedback_store()
            from models import FeedbackCreate
            fb.submit(FeedbackCreate(
                query_id=query_id,
                rating=rating,
                comment=f"来自飞书 Bot — {sender_id}",
            ))
            logger.info("bot_feedback_recorded", rating=rating, query_id=query_id)
        except Exception as e:  # noqa: BLE001  # Bot 反馈落盘失败仅记录错误，不阻断消息处理
            logger.error("bot_feedback_failed", error=str(e))

        return None

    # ── RAG Query ──────────────────────────────────────────────────────

    def _rag_query(self, query: str) -> tuple[str, list[str]]:
        """Run RAG query and return (answer, list of source labels)."""
        try:
            from embedding import EmbeddingClient
            from vector_store import VectorStore
            from retrieval import RetrievalPipeline, RetrievalConfig
            from generator import RAGGenerator, GenerationConfig

            ec = EmbeddingClient()
            vs = VectorStore()
            config = RetrievalConfig(enable_cross_encoder=True, max_total_candidates=8)
            pipeline = RetrievalPipeline(vector_store=vs, embedding_client=ec, config=config)
            gen_config = GenerationConfig(
                model=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
                api_key=os.getenv("LANGEXTRACT_API_KEY", ""),
                base_url=os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
            )
            generator = RAGGenerator(pipeline, config=gen_config)
            result = generator.generate(query)

            answer = result.get("answer", "抱歉，未找到相关信息。")
            sources = [s.get("text_snippet", "")[:100] for s in result.get("sources", [])]
            return answer, sources
        except Exception as e:  # noqa: BLE001  # Bot RAG 管线异常统一降级为兜底文案，不向用户暴露内部错误
            logger.error("bot_rag_pipeline_error", error=str(e))
            return "抱歉，查询失败，请稍后重试。", []
