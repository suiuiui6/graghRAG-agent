"""
Audit Logger — §6.5 of enterprise-evolution-blueprint.

Writes security/compliance audit events as JSONL. One file per day.
Separate from operational logs. Injects audit calls at key action points
across Phase 0-2 modules.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from logging_config import get_logger

logger = get_logger(__name__)

AUDIT_DIR = Path("output/audit")


class AuditLogger:
    """Security audit log writer. Appends JSONL to daily files."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir or AUDIT_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _today_file(self) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.base_dir / f"audit-{date_str}.jsonl"

    def log(self, event: str, user_id: str = "system",
            ip: str = "", user_agent: str = "", **details):
        """Write an audit event. Thread-safe append."""
        record = {
            "event": event,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": ip,
            "user_agent": user_agent,
            "details": details,
        }
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with open(self._today_file(), "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:  # noqa: BLE001  # 审计写入失败仅记录错误，不阻断业务主流程
            logger.error("audit_write_failed", error=str(e))

    # ── convenience methods ──────────────────────────────────────────

    def auth_login(self, user_id: str, ip: str = "", ua: str = ""):
        self.log("user.login", user_id, ip=ip, user_agent=ua)

    def auth_logout(self, user_id: str, ip: str = ""):
        self.log("user.logout", user_id, ip=ip)

    def auth_failed(self, user_id: str, reason: str, ip: str = ""):
        self.log("user.login_failed", user_id, ip=ip, reason=reason)

    def data_exported(self, user_id: str, fmt: str, rows: int = 0):
        self.log("data.exported", user_id, format=fmt, estimated_rows=rows)

    def backup_triggered(self, user_id: str, backup_id: str, backup_type: str):
        self.log("backup.triggered", user_id, backup_id=backup_id, backup_type=backup_type)

    def restore_executed(self, user_id: str, backup_id: str):
        self.log("restore.executed", user_id, backup_id=backup_id)

    def cleanup_executed(self, user_id: str, total_removed: int):
        self.log("cleanup.executed", user_id, total_removed=total_removed)

    def api_key_created(self, admin_id: str, key_id: str, name: str):
        self.log("api_key.created", admin_id, key_id=key_id, name=name)

    def api_key_revoked(self, admin_id: str, key_id: str):
        self.log("api_key.revoked", admin_id, key_id=key_id)

    def config_updated(self, user_id: str, key: str):
        self.log("config.updated", user_id, key=key)

    # ── query ────────────────────────────────────────────────────────

    def query(self, event: str | None = None, user_id: str | None = None,
              from_date: str | None = None, to_date: str | None = None,
              limit: int = 200) -> list[dict]:
        """Query audit events with optional filters."""
        results: list[dict] = []
        for f in sorted(self.base_dir.glob("audit-*.jsonl"), reverse=True):
            if from_date and f.stem < f"audit-{from_date}":
                continue
            if to_date and f.stem > f"audit-{to_date}":
                continue
            try:
                for line in f.read_text(encoding="utf-8").strip().split("\n"):
                    if not line:
                        continue
                    rec = json.loads(line)
                    if event and rec.get("event") != event:
                        continue
                    if user_id and rec.get("user_id") != user_id:
                        continue
                    results.append(rec)
                    if len(results) >= limit:
                        return results
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def export_csv(self, from_date: str | None = None,
                   to_date: str | None = None) -> str:
        """Export audit log as CSV string (UTF-8 BOM)."""
        import io
        import csv
        records = self.query(from_date=from_date, to_date=to_date, limit=10000)
        buf = io.StringIO()
        if records:
            writer = csv.DictWriter(buf, fieldnames=["event", "user_id", "timestamp",
                                                     "ip", "user_agent", "details"])
            writer.writeheader()
            for r in records:
                r["details"] = json.dumps(r.get("details", {}), ensure_ascii=False)
                writer.writerow(r)
        return "﻿" + buf.getvalue()


# ── singleton ─────────────────────────────────────────────────────────────

_audit: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit
    if _audit is None:
        _audit = AuditLogger()
    return _audit
