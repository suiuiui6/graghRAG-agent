"""
Backup Manager — §5.4 of enterprise-evolution-blueprint.

tar.gz full backup with manifest, incremental KG version backup, restore
with pre-restore snapshot, and backup verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import BackupManifest, BackupResult, RestoreResult
from logging_config import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path("output")
BACKUP_DIR = OUTPUT_DIR / "backups"
BACKUP_MANIFEST = {
    "kg": {"path": "output/kg/", "strategy": "incremental_version"},
    "vectordb": {"path": "output/vectordb/", "strategy": "full"},
    "feedback": {"path": "output/feedback/", "strategy": "full"},
    "conversations": {"path": "output/conversations/", "strategy": "full"},
    "logs": {"path": "output/logs/", "strategy": "rotate_only"},
    "embedding_cache": {"path": "output/embedding_cache/", "strategy": "skip"},
    "docs_store": {"path": "output/docs_store.json", "strategy": "full"},
    "tasks_store": {"path": "output/tasks_store.json", "strategy": "full"},
}


class BackupManager:
    """tar.gz backup, restore, and verification."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or BACKUP_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _cleanup_directory(self, path: Path, *, required: bool) -> bool:
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except PermissionError as exc:
            logger.warning("backup_cleanup_permission_denied", path=str(path), error=str(exc))
            if required:
                raise
        except OSError as exc:
            logger.warning("backup_cleanup_failed", path=str(path), error=str(exc))
            if required:
                raise
        return False

    def _delete_backup_file(self, path: Path) -> bool:
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except PermissionError as exc:
            logger.warning("backup_retention_permission_denied", path=str(path), error=str(exc))
        except OSError as exc:
            logger.warning("backup_retention_delete_failed", path=str(path), error=str(exc))
        return False

    # ── backup ──────────────────────────────────────────────────────────

    def create_backup(self, backup_type: str = "manual") -> BackupResult:
        bid = f"{backup_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        backup_dir = self.base_dir / bid
        backup_dir.mkdir(parents=True, exist_ok=True)

        total_files = 0
        total_size = 0
        dirs_backed_up: list[str] = []

        try:
            for name, cfg in BACKUP_MANIFEST.items():
                if cfg["strategy"] == "skip":
                    continue
                p = Path(cfg["path"])
                if not p.exists():
                    continue
                if cfg["strategy"] == "rotate_only":
                    continue

                if cfg["strategy"] == "incremental_version":
                    # Only back up active versions
                    for doc_dir in sorted(p.iterdir()):
                        if not doc_dir.is_dir() or not doc_dir.name.startswith("doc_"):
                            continue
                        versions_file = doc_dir / "versions.json"
                        if versions_file.exists():
                            vs_data = json.loads(versions_file.read_text(encoding="utf-8"))
                            active_v = vs_data.get("active_version", 1)
                            v_dir = doc_dir / f"v{active_v}"
                            if v_dir.exists():
                                dest = backup_dir / "kg" / doc_dir.name / f"v{active_v}"
                                dest.mkdir(parents=True, exist_ok=True)
                                for f in v_dir.iterdir():
                                    shutil.copy2(f, dest / f.name)
                                    total_files += 1
                                    total_size += f.stat().st_size
                            shutil.copy2(versions_file, backup_dir / "kg" / doc_dir.name / "versions.json")
                else:
                    # full strategy
                    dest = backup_dir / name
                    if p.is_dir():
                        shutil.copytree(p, dest, dirs_exist_ok=True)
                        for root, _ds, files in os.walk(dest):
                            for f in files:
                                total_files += 1
                                total_size += Path(root, f).stat().st_size
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dest)
                        total_files += 1
                        total_size += p.stat().st_size

                dirs_backed_up.append(name)

            manifest = BackupManifest(
                backup_id=bid,
                created_at=self._now(),
                backup_type=backup_type,
                directories=dirs_backed_up,
                total_files=total_files,
                total_size_bytes=total_size,
            )

            (backup_dir / "manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8")

            tar_path = self.base_dir / f"{bid}.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=bid)

            checksum = hashlib.sha256(tar_path.read_bytes()).hexdigest()[:16]
            manifest.checksum = checksum

            # Once the archive exists, staging cleanup is housekeeping rather than core success.
            self._cleanup_directory(backup_dir, required=False)

            logger.info("backup_created", backup_id=bid, files=total_files,
                        size_mb=round(total_size / 1024 / 1024, 2))
            try:
                from services.event_bus import get_event_bus
                get_event_bus().publish("backup.completed", {
                    "backup_id": bid,
                    "backup_type": backup_type,
                    "total_files": total_files,
                    "total_size_bytes": total_size,
                    "checksum": checksum,
                })
            except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响备份结果返回
                pass
            try:
                from services.audit_logger import get_audit_logger
                get_audit_logger().log("backup.triggered", backup_id=bid,
                                       backup_type=backup_type, files=total_files)
            except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
                pass
            return BackupResult(backup_id=bid, status="completed", manifest=manifest)

        except Exception as e:  # noqa: BLE001  # 备份失败已记录并返回 failed 结果，异常不再向上冒泡
            logger.error("backup_failed", error=str(e))
            try:
                from services.event_bus import get_event_bus
                get_event_bus().publish("backup.failed", {
                    "backup_id": bid, "backup_type": backup_type, "error": str(e),
                })
            except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响失败结果返回
                pass
            if backup_dir.exists():
                self._cleanup_directory(backup_dir, required=False)
            return BackupResult(backup_id=bid, status="failed", error=str(e))

    # ── list ────────────────────────────────────────────────────────────

    def list_backups(self) -> list[dict]:
        result = []
        for f in sorted(self.base_dir.glob("*.tar.gz"), key=os.path.getmtime, reverse=True):
            result.append({
                "backup_id": f.name[:-7],
                "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
                "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        return result

    def get_manifest(self, backup_id: str) -> dict | None:
        tar_path = self.base_dir / f"{backup_id}.tar.gz"
        if not tar_path.exists():
            return None
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                m_path = f"{backup_id}/manifest.json"
                if m_path in tar.getnames():
                    manifest_file = tar.extractfile(m_path)
                    if manifest_file is not None:
                        return json.loads(manifest_file.read())
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass
        return None

    # ── restore ─────────────────────────────────────────────────────────

    def restore(self, backup_id: str) -> RestoreResult:
        tar_path = self.base_dir / f"{backup_id}.tar.gz"
        if not tar_path.exists():
            return RestoreResult(status="failed", restored_from=backup_id,
                                error="Backup not found")

        snapshot_id = f".pre-restore-{uuid4().hex[:8]}"
        snapshot_dir = self.base_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            for name, cfg in BACKUP_MANIFEST.items():
                p = Path(cfg["path"])
                if p.exists():
                    dest = snapshot_dir / name
                    if p.is_dir():
                        shutil.copytree(p, dest)
                    else:
                        shutil.copy2(p, dest)
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                # filter="data" 由 Python 3.12 提供，拒绝绝对路径、.. 穿越、
                # 指向基目录外的符号链接与设备文件 —— 防恶意/损坏备份包写到
                # 目标目录之外（bandit B202）。不要回退成无 filter 的 extractall。
                tar.extractall(path=self.base_dir, filter="data")

            extracted = self.base_dir / backup_id
            for item in extracted.iterdir():
                if item.name == "manifest.json":
                    continue
                dest = Path(BACKUP_MANIFEST.get(item.name, {}).get("path", f"output/{item.name}"))
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            shutil.rmtree(extracted)
            logger.info("backup_restored", backup_id=backup_id, snapshot=snapshot_id)
            try:
                from services.audit_logger import get_audit_logger
                get_audit_logger().log("restore.executed", backup_id=backup_id, snapshot=snapshot_id)
            except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
                pass
            return RestoreResult(status="completed", restored_from=backup_id,
                                pre_restore_snapshot=snapshot_id)

        except Exception as e:  # noqa: BLE001  # 恢复失败已记录并返回 failed 结果，异常不再向上冒泡
            logger.error("restore_failed", error=str(e))
            return RestoreResult(status="failed", restored_from=backup_id,
                                error=str(e))

    # ── verify ───────────────────────────────────────────────────────────

    def verify(self, backup_id: str) -> dict:
        tar_path = self.base_dir / f"{backup_id}.tar.gz"
        if not tar_path.exists():
            return {"backup_id": backup_id, "valid": False, "error": "File not found"}

        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                names = tar.getnames()
                has_manifest = f"{backup_id}/manifest.json" in names
                has_kg = any(f"{backup_id}/kg/" in n for n in names)

                manifest = None
                if has_manifest:
                    manifest_file = tar.extractfile(f"{backup_id}/manifest.json")
                    if manifest_file is not None:
                        manifest = json.loads(manifest_file.read())

                return {
                    "backup_id": backup_id,
                    "valid": has_manifest,
                    "size_mb": round(tar_path.stat().st_size / 1024 / 1024, 2),
                    "has_manifest": has_manifest,
                    "has_kg": has_kg,
                    "file_count": len(names),
                    "manifest": manifest,
                }
        except Exception as e:  # noqa: BLE001  # 校验失败即返回 valid=False 及错误信息，由调用方判定
            return {"backup_id": backup_id, "valid": False, "error": str(e)}

    # ── cleanup ─────────────────────────────────────────────────────────

    def cleanup_old_backups(self, keep_daily: int = 7, keep_weekly: int = 4) -> int:
        """Remove expired backups. Returns count of removed."""
        removed = 0
        backups = sorted(self.base_dir.glob("*.tar.gz"), key=os.path.getmtime, reverse=True)

        daily_backups = [b for b in backups if "daily" in b.name or
                        "daily" not in b.name and "weekly" not in b.name and "manual" not in b.name]
        weekly_backups = [b for b in backups if "weekly" in b.name]

        for b in daily_backups[keep_daily:]:
            if b.exists() and self._delete_backup_file(b):
                removed += 1

        for b in weekly_backups[keep_weekly:]:
            if b.exists() and self._delete_backup_file(b):
                removed += 1

        return removed

    # ── scheduled backup ────────────────────────────────────────────────

    def scheduled_backup(self) -> BackupResult:
        """Run the daily scheduled backup (called by APScheduler)."""
        self.cleanup_old_backups()
        return self.create_backup(backup_type="daily")


_manager: BackupManager | None = None


def get_backup_manager() -> BackupManager:
    global _manager
    if _manager is None:
        _manager = BackupManager()
    return _manager
