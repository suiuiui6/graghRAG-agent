"""
Feedback Store — §4.1 of enterprise-evolution-blueprint.

JSON file persistence under output/feedback/. Each feedback entry gets
its own file. State machine: open → acknowledged → resolved.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import FeedbackCreate, FeedbackRecord, FeedbackUpdate

from logging_config import get_logger

logger = get_logger(__name__)

FEEDBACK_DIR = Path("output/feedback")


class FeedbackStore:
    """File-based feedback storage with status tracking."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or FEEDBACK_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, feedback_id: str) -> Path:
        return self.base_dir / f"{feedback_id}.json"

    def submit(self, data: FeedbackCreate, query_text: str = "", answer_text: str = "") -> FeedbackRecord:
        fid = uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        rec = FeedbackRecord(
            feedback_id=fid,
            created_at=now,
            query_text=query_text,
            answer_text=answer_text,
            status="open",
            **data.model_dump(),
        )
        self._save(rec)
        logger.info("feedback_submitted", feedback_id=fid, rating=data.rating)
        # Publish event + audit log
        try:
            from services.event_bus import get_event_bus
            get_event_bus().publish("feedback.received", {
                "feedback_id": fid,
                "query_id": data.query_id,
                "rating": data.rating,
                "comment": data.comment,
                "user_id": data.user_id,
            })
        except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响反馈提交返回
            pass
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().log("feedback.received", feedback_id=fid,
                                   query_id=data.query_id, rating=data.rating)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
        return rec

    def _save(self, rec: FeedbackRecord) -> None:
        p = self._path(rec.feedback_id)
        p.write_text(rec.model_dump_json(indent=2), encoding="utf-8")

    def get(self, feedback_id: str) -> FeedbackRecord | None:
        p = self._path(feedback_id)
        if not p.exists():
            return None
        return FeedbackRecord(**json.loads(p.read_text(encoding="utf-8")))

    def update(self, feedback_id: str, update: FeedbackUpdate) -> FeedbackRecord | None:
        rec = self.get(feedback_id)
        if rec is None:
            return None
        if update.status is not None:
            rec.status = update.status
        self._save(rec)
        logger.info("feedback_updated", feedback_id=feedback_id, status=rec.status)
        if update.status == "resolved":
            try:
                from services.event_bus import get_event_bus
                get_event_bus().publish("feedback.resolved", {
                    "feedback_id": feedback_id, "query_id": rec.query_id,
                })
            except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响状态更新返回
                pass
            try:
                from services.audit_logger import get_audit_logger
                get_audit_logger().log("feedback.resolved", feedback_id=feedback_id)
            except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
                pass
        return rec

    def list_all(self, status: str | None = None, limit: int = 50) -> list[FeedbackRecord]:
        result = []
        for f in sorted(self.base_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                rec = FeedbackRecord(**json.loads(f.read_text(encoding="utf-8")))
                if status and rec.status != status:
                    continue
                result.append(rec)
                if len(result) >= limit:
                    break
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return result

    def stats(self) -> dict:
        total = 0
        positive = 0
        negative = 0
        by_status = {"open": 0, "acknowledged": 0, "resolved": 0}
        recent_negative = []

        for f in sorted(self.base_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                rec = FeedbackRecord(**json.loads(f.read_text(encoding="utf-8")))
                total += 1
                if rec.rating == "positive":
                    positive += 1
                else:
                    negative += 1
                    if len(recent_negative) < 10:
                        recent_negative.append(rec)
                by_status[rec.status] = by_status.get(rec.status, 0) + 1
            except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                pass

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "positive_ratio": positive / total if total > 0 else 0.0,
            "by_status": by_status,
            "recent_negative": [r.model_dump() for r in recent_negative],
        }

    def delete(self, feedback_id: str) -> bool:
        p = self._path(feedback_id)
        if p.exists():
            p.unlink()
            return True
        return False


# ── singleton ─────────────────────────────────────────────────────────────

_store: FeedbackStore | None = None


def get_feedback_store() -> FeedbackStore:
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store
