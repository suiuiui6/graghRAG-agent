"""
Webhook Manager — §6.3 of enterprise-evolution-blueprint.

CRUD for webhook subscriptions, HMAC signing, delivery tracking.
Storage: output/webhooks/{webhook_id}.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import WebhookCreate, WebhookRecord, DeliveryLog
from logging_config import get_logger

logger = get_logger(__name__)

WEBHOOKS_DIR = Path("output/webhooks")


class WebhookManager:
    """Manage webhook subscriptions and delivery logs."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or WEBHOOKS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _path(self, webhook_id: str) -> Path:
        return self.base_dir / f"{webhook_id}.json"

    def _deliveries_path(self, webhook_id: str) -> Path:
        return self.base_dir / f"{webhook_id}_deliveries.jsonl"

    def _read_payload(self, webhook_id: str) -> dict | None:
        p = self._path(webhook_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def _is_deleted_payload(self, payload: dict | None) -> bool:
        return bool(payload and payload.get("deleted_at"))

    # ── CRUD ──────────────────────────────────────────────────────────

    def create(self, data: WebhookCreate) -> WebhookRecord:
        rec = WebhookRecord(
            webhook_id=uuid4().hex[:12],
            url=data.url,
            events=data.events,
            secret=data.secret,
            description=data.description,
            created_at=self._now(),
        )
        self._save(rec)
        logger.info("webhook_registered", webhook_id=rec.webhook_id, events=data.events)
        return rec

    def list_all(self) -> list[WebhookRecord]:
        results = []
        for f in sorted(self.base_dir.glob("*.json")):
            if "_deliveries" in f.name:
                continue
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
                if self._is_deleted_payload(payload):
                    continue
                results.append(WebhookRecord(**payload))
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def get(self, webhook_id: str) -> WebhookRecord | None:
        payload = self._read_payload(webhook_id)
        if payload is None or self._is_deleted_payload(payload):
            return None
        try:
            return WebhookRecord(**payload)
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def update(self, webhook_id: str, data: WebhookCreate) -> WebhookRecord | None:
        rec = self.get(webhook_id)
        if not rec:
            return None
        rec.url = data.url
        rec.events = data.events
        rec.secret = data.secret
        rec.description = data.description
        self._save(rec)
        return rec

    def delete(self, webhook_id: str) -> bool:
        payload = self._read_payload(webhook_id)
        if payload is None:
            return True

        payload["enabled"] = False
        payload["deleted_at"] = self._now()
        self._path(webhook_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        dp = self._deliveries_path(webhook_id)
        if dp.exists():
            try:
                dp.unlink()
            except (PermissionError, OSError) as exc:
                logger.warning("webhook_delivery_cleanup_failed", webhook_id=webhook_id, error=str(exc))
        return True

    def get_matching(self, event_type: str) -> list[dict]:
        """Return all enabled webhooks subscribed to this event type."""
        matching = []
        for wh in self.list_all():
            if not wh.enabled:
                continue
            if event_type in wh.events or "*" in wh.events:
                matching.append(wh.model_dump())
        return matching

    # ── delivery tracking ─────────────────────────────────────────────

    def record_delivery(self, webhook_id: str, delivery: DeliveryLog):
        dp = self._deliveries_path(webhook_id)
        with open(dp, "a", encoding="utf-8") as f:
            f.write(delivery.model_dump_json() + "\n")

        rec = self.get(webhook_id)
        if rec:
            rec.last_delivery_at = delivery.timestamp
            rec.delivery_count += 1
            if delivery.status == "failed":
                rec.failed_count += 1
            self._save(rec)

    def get_deliveries(self, webhook_id: str, limit: int = 50) -> list[DeliveryLog]:
        dp = self._deliveries_path(webhook_id)
        if not dp.exists():
            return []
        results = []
        try:
            lines = dp.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines):
                if not line:
                    continue
                results.append(DeliveryLog(**json.loads(line)))
                if len(results) >= limit:
                    break
        except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            pass
        return results

    # ── test ping ─────────────────────────────────────────────────────

    def test_ping(self, webhook_id: str) -> dict:
        """Send a test event to the webhook URL."""
        import requests
        rec = self.get(webhook_id)
        if not rec:
            return {"status": "error", "message": "Webhook not found"}

        event = {
            "event_id": uuid4().hex[:12],
            "event_type": "test.ping",
            "timestamp": self._now(),
            "source": "graphrag-backend",
            "version": "1.0",
            "data": {"message": "Webhook test ping from GraphRAG"},
        }
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")

        headers = {"Content-Type": "application/json",
                   "X-GraphRAG-Event": "test.ping"}
        if rec.secret:
            import hmac
            import hashlib
            sig = hmac.new(rec.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-GraphRAG-Signature"] = f"sha256={sig}"

        try:
            resp = requests.post(rec.url, data=body, headers=headers, timeout=10)
            return {"status": "ok" if resp.ok else "failed",
                    "http_status": resp.status_code,
                    "response": resp.text[:500]}
        except Exception as e:  # noqa: BLE001  # webhook 测试投递失败以 error 状态返回结果体，不向调用方抛异常
            return {"status": "error", "message": str(e)[:200]}

    def _save(self, rec: WebhookRecord) -> None:
        self._path(rec.webhook_id).write_text(rec.model_dump_json(indent=2), encoding="utf-8")


_manager: WebhookManager | None = None


def get_webhook_manager() -> WebhookManager:
    global _manager
    if _manager is None:
        _manager = WebhookManager()
    return _manager
