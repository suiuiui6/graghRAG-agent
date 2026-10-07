"""
Event Bus — §6.3 of enterprise-evolution-blueprint.

Publish/subscribe event system with async delivery, exponential backoff retry,
and JSONL event logging. Integrated into FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import WebhookEvent, DeliveryLog
from logging_config import get_logger

logger = get_logger(__name__)

EVENTS_DIR = Path("output/events")


class EventBus:
    """Publish events + async delivery to subscribed webhooks."""

    def __init__(self):
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        self._queue: asyncio.Queue[tuple[WebhookEvent, dict]] = asyncio.Queue(maxsize=1000)
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        """Start the background delivery worker."""
        self._worker_task = asyncio.create_task(self._delivery_loop())
        logger.info("event_bus_started")

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("event_bus_stopped")

    def publish(self, event_type: str, data: dict) -> WebhookEvent:
        """Publish an event. Non-blocking — delivery happens in background."""
        event = WebhookEvent(
            event_id=uuid4().hex[:12],
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
        )

        # Write to event log
        self._write_event_log(event)

        # Find matching webhooks and enqueue
        try:
            from services.webhook_manager import get_webhook_manager
            wm = get_webhook_manager()
            for wh in wm.get_matching(event_type):
                try:
                    self._queue.put_nowait((event, wh))
                except asyncio.QueueFull:
                    logger.warning("event_queue_full", event_type=event_type)
        except Exception as e:  # noqa: BLE001  # 事件发布失败仅记录错误，不阻断业务主流程
            logger.error("event_publish_error", error=str(e))

        logger.debug("event_published", event_type=event_type, event_id=event.event_id)
        return event

    # ── delivery worker ────────────────────────────────────────────────

    async def _delivery_loop(self):
        while True:
            try:
                event, wh_config = await self._queue.get()
                await self._deliver(event, wh_config)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001  # 投递循环单次异常仅记录并继续处理后续事件，保证后台 worker 存活
                logger.error("delivery_loop_error", error=str(e))

    async def _deliver(self, event: WebhookEvent, wh_config: dict):
        import hmac
        import hashlib
        import httpx

        url = wh_config.get("url", "")
        secret = wh_config.get("secret", "")
        wh_id = wh_config.get("webhook_id", "unknown")
        body = event.model_dump_json().encode("utf-8")

        # HMAC signature
        signature = ""
        if secret:
            sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            signature = f"sha256={sig}"

        headers = {
            "Content-Type": "application/json",
            "X-GraphRAG-Event": event.event_type,
            "X-GraphRAG-Event-ID": event.event_id,
        }
        if signature:
            headers["X-GraphRAG-Signature"] = signature

        backoffs = [1, 5, 25, 125]  # seconds
        for attempt, delay in enumerate(backoffs):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, content=body, headers=headers)
                delivery = DeliveryLog(
                    delivery_id=uuid4().hex[:8],
                    webhook_id=wh_id,
                    event_id=event.event_id,
                    status="success" if 200 <= resp.status_code < 300 else "failed",
                    attempt=attempt + 1,
                    status_code=resp.status_code,
                    error=None if 200 <= resp.status_code < 300 else f"HTTP {resp.status_code}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                self._save_delivery(wh_id, delivery)
                if 200 <= resp.status_code < 300:
                    return
            except Exception as e:  # noqa: BLE001  # 投递失败已记录该次 DeliveryLog 并进入退避重试，异常不再向外抛出
                delivery = DeliveryLog(
                    delivery_id=uuid4().hex[:8],
                    webhook_id=wh_id,
                    event_id=event.event_id,
                    status="failed",
                    attempt=attempt + 1,
                    error=str(e)[:200],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                self._save_delivery(wh_id, delivery)

            if attempt < len(backoffs) - 1:
                await asyncio.sleep(delay)

        logger.warning("webhook_delivery_exhausted", webhook_id=wh_id, event_id=event.event_id)

    # ── persistence ────────────────────────────────────────────────────

    def _write_event_log(self, event: WebhookEvent):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = EVENTS_DIR / f"events-{date_str}.jsonl"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception:  # noqa: S110, BLE001  # 事件日志落盘为尽力而为，写失败仅丢失审计追溯，不影响投递
            pass

    def _save_delivery(self, webhook_id: str, delivery: DeliveryLog):
        try:
            from services.webhook_manager import get_webhook_manager
            get_webhook_manager().record_delivery(webhook_id, delivery)
        except Exception:  # noqa: S110, BLE001  # 投递记录持久化为旁路，失败不中断已发起的 webhook 投递
            pass


# ── singleton ─────────────────────────────────────────────────────────────

_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
