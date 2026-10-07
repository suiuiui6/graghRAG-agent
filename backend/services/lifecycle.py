"""
Data Lifecycle Manager — §5.6 of enterprise-evolution-blueprint.

Enforces retention policies for all data categories. Provides dry-run
preview and automated cleanup via APScheduler.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import CleanupPreview, CleanupReport, StorageReport
from logging_config import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path("output")
CONVERSATIONS_DIR = OUTPUT_DIR / "conversations"
FEEDBACK_DIR = OUTPUT_DIR / "feedback"
KG_DIR = OUTPUT_DIR / "kg"
LOGS_DIR = OUTPUT_DIR / "logs"
BACKUP_DIR = OUTPUT_DIR / "backups"


class DataLifecycleManager:
    """Centralized data retention policy enforcement."""

    RETENTION_POLICIES = {
        "conversations": {
            "max_age_days": 7,
            "keep_if_feedback": True,
            "description": "Inactive conversations older than 7 days",
        },
        "feedback": {
            "max_age_days": None,  # permanent
            "keep_if_feedback": False,
            "description": "Feedback is kept permanently",
        },
        "kg_versions": {
            "max_versions": 10,
            "keep_active": True,
            "description": "Keep at most 10 versions per document",
        },
        "query_history": {
            "max_age_days": 90,
            "keep_if_feedback": True,
            "description": "Query history older than 90 days",
        },
        "logs": {
            "max_age_days": 30,
            "keep_if_feedback": False,
            "description": "Log files older than 30 days",
        },
        "audit": {
            "max_age_days": 365,
            "keep_if_feedback": False,
            "description": "Audit logs older than 365 days",
        },
        "backups": {
            "daily_keep": 7,
            "weekly_keep": 4,
            "description": "Daily backups 7 days, weekly 4 weeks",
        },
    }

    def __init__(self):
        self._now = datetime.now(timezone.utc)

    # ── cleanup ──────────────────────────────────────────────────────────

    def run_cleanup(self) -> CleanupReport:
        """Execute all retention policies. Returns cleanup report."""
        errors: list[str] = []
        categories: dict[str, int] = {}

        try:
            categories["conversations"] = self._clean_conversations()
        except Exception as e:  # noqa: BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            errors.append(f"conversations: {e}")

        try:
            categories["kg_versions"] = self._clean_kg_versions()
        except Exception as e:  # noqa: BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            errors.append(f"kg_versions: {e}")

        try:
            categories["logs"] = self._clean_logs()
        except Exception as e:  # noqa: BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            errors.append(f"logs: {e}")

        try:
            categories["backups"] = self._clean_backups()
        except Exception as e:  # noqa: BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            errors.append(f"backups: {e}")

        try:
            categories["audit"] = self._clean_audit()
        except Exception as e:  # noqa: BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            errors.append(f"audit: {e}")

        total = sum(categories.values())
        report = CleanupReport(
            executed_at=datetime.now(timezone.utc).isoformat(),
            categories=categories,
            total_removed=total,
            errors=errors,
        )

        logger.info("cleanup_executed", total_removed=total, categories=categories)
        # Publish event + audit log
        try:
            from services.event_bus import get_event_bus
            get_event_bus().publish("cleanup.executed", {
                "total_removed": total, "categories": categories, "errors": errors,
            })
        except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响清理结果返回
            pass
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().log("cleanup.executed", total_removed=total, categories=categories)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
        return report

    def preview_cleanup(self) -> list[CleanupPreview]:
        """Dry-run: show what would be cleaned without deleting."""
        previews: list[CleanupPreview] = []

        # Conversations
        expired_convs = self._find_expired_conversations()
        previews.append(CleanupPreview(
            category="conversations",
            policy={"max_age_days": 7, "keep_if_feedback": True},
            items_to_remove=len(expired_convs),
            items_sample=[c.name for c in expired_convs[:10]],
        ))

        # KG versions
        expired_versions = self._find_expired_versions()
        previews.append(CleanupPreview(
            category="kg_versions",
            policy={"max_versions": 10, "keep_active": True},
            items_to_remove=len(expired_versions),
            items_sample=expired_versions[:10],
        ))

        # Logs
        expired_logs = self._find_expired_logs()
        previews.append(CleanupPreview(
            category="logs",
            policy={"max_age_days": 30},
            items_to_remove=len(expired_logs),
            items_sample=[p.name for p in expired_logs[:10]],
        ))

        # Backups
        expired_backups = self._find_expired_backups()
        previews.append(CleanupPreview(
            category="backups",
            policy={"daily_keep": 7, "weekly_keep": 4},
            items_to_remove=len(expired_backups),
            items_sample=[b.name for b in expired_backups[:10]],
        ))

        # Audit logs
        expired_audit = self._find_expired_audit()
        previews.append(CleanupPreview(
            category="audit",
            policy={"max_age_days": 365},
            items_to_remove=len(expired_audit),
            items_sample=[a.name for a in expired_audit[:10]],
        ))

        return previews

    # ── conversations ────────────────────────────────────────────────────

    def _clean_conversations(self) -> int:
        removed = 0
        expired = self._find_expired_conversations()
        for p in expired:
            try:
                p.unlink()
                removed += 1
            except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
                pass
        return removed

    def _find_expired_conversations(self) -> list[Path]:
        expired: list[Path] = []
        if not CONVERSATIONS_DIR.exists():
            return expired

        cutoff = self._now - timedelta(days=7)
        for f in CONVERSATIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                # Keep if has feedback
                if data.get("has_feedback"):
                    continue
                last = data.get("last_active", "")
                if last:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if last_dt < cutoff:
                        expired.append(f)
                elif f.stat().st_mtime < cutoff.timestamp():
                    expired.append(f)
            except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                # Corrupt file, safe to clean if old
                if f.stat().st_mtime < cutoff.timestamp():
                    expired.append(f)
        return expired

    # ── KG versions ──────────────────────────────────────────────────────

    def _clean_kg_versions(self) -> int:
        removed = 0
        expired = self._find_expired_versions()
        for version_dir in expired:
            try:
                shutil.rmtree(version_dir)
                removed += 1
            except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
                pass
        return removed

    def _find_expired_versions(self) -> list[str]:
        expired: list[str] = []
        if not KG_DIR.exists():
            return expired

        for doc_dir in sorted(KG_DIR.iterdir()):
            if not doc_dir.is_dir() or not doc_dir.name.startswith("doc_"):
                continue
            versions = sorted(
                [d for d in doc_dir.iterdir() if d.is_dir() and d.name.startswith("v")],
                key=lambda x: int(x.name[1:]) if x.name[1:].isdigit() else 0,
            )
            if len(versions) <= 10:
                continue
            # Keep last 10, remove oldest
            for v in versions[:-10]:
                expired.append(str(v.relative_to(KG_DIR)))
        return expired

    # ── logs ─────────────────────────────────────────────────────────────

    def _clean_logs(self) -> int:
        removed = 0
        expired = self._find_expired_logs()
        for p in expired:
            try:
                p.unlink()
                removed += 1
            except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
                pass
        return removed

    def _find_expired_logs(self) -> list[Path]:
        expired: list[Path] = []
        if not LOGS_DIR.exists():
            return expired
        cutoff = self._now - timedelta(days=30)
        for f in LOGS_DIR.glob("*.log*"):
            if f.stat().st_mtime < cutoff.timestamp():
                expired.append(f)
        return expired

    # ── audit ─────────────────────────────────────────────────────────────

    AUDIT_DIR = OUTPUT_DIR / "audit"

    def _clean_audit(self) -> int:
        removed = 0
        expired = self._find_expired_audit()
        for p in expired:
            try:
                p.unlink()
                removed += 1
            except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
                pass
        return removed

    def _find_expired_audit(self) -> list[Path]:
        expired: list[Path] = []
        if not self.AUDIT_DIR.exists():
            return expired
        cutoff = self._now - timedelta(days=365)
        for f in self.AUDIT_DIR.glob("audit-*.jsonl"):
            if f.stat().st_mtime < cutoff.timestamp():
                expired.append(f)
        return expired

    # ── backups ──────────────────────────────────────────────────────────

    def _clean_backups(self) -> int:
        from services.backup import get_backup_manager
        return get_backup_manager().cleanup_old_backups()

    def _find_expired_backups(self) -> list[Path]:
        from services.backup import get_backup_manager
        mgr = get_backup_manager()
        backups = sorted(mgr.base_dir.glob("*.tar.gz"), key=os.path.getmtime, reverse=True)
        expired: list[Path] = []
        daily_count = 0
        weekly_count = 0
        for b in backups:
            if "weekly" in b.name:
                weekly_count += 1
                if weekly_count > 4:
                    expired.append(b)
            else:
                daily_count += 1
                if daily_count > 7:
                    expired.append(b)
        return expired

    # ── storage report ───────────────────────────────────────────────────

    def storage_report(self) -> StorageReport:
        dirs: dict[str, dict] = {}
        total = 0

        dirs_to_check = [
            ("kg", KG_DIR),
            ("vectordb", OUTPUT_DIR / "vectordb"),
            ("feedback", FEEDBACK_DIR),
            ("conversations", CONVERSATIONS_DIR),
            ("logs", LOGS_DIR),
            ("backups", BACKUP_DIR),
            ("audit", OUTPUT_DIR / "audit"),
            ("embedding_cache", OUTPUT_DIR / "embedding_cache"),
        ]

        for name, path in dirs_to_check:
            size = self._dir_size(path) if path.exists() else 0
            file_count = self._file_count(path) if path.exists() else 0
            dirs[name] = {"size_bytes": size, "size_mb": round(size / 1024 / 1024, 2),
                         "files": file_count}
            total += size

        return StorageReport(
            directories=dirs,
            total_size_bytes=total,
            last_checked=datetime.now(timezone.utc).isoformat(),
        )

    def _dir_size(self, path: Path) -> int:
        total = 0
        try:
            for root, _ds, files in os.walk(path):
                for f in files:
                    fp = Path(root) / f
                    if fp.exists():
                        total += fp.stat().st_size
        except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            pass
        return total

    def _file_count(self, path: Path) -> int:
        count = 0
        try:
            for root, _ds, files in os.walk(path):
                count += len(files)
        except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            pass
        return count


# ── singleton ─────────────────────────────────────────────────────────────

_manager: DataLifecycleManager | None = None


def get_lifecycle_manager() -> DataLifecycleManager:
    global _manager
    if _manager is None:
        _manager = DataLifecycleManager()
    return _manager
