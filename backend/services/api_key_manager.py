"""
API Key Manager — §6.6 of enterprise-evolution-blueprint.

Multi-key management with scoped permissions, rate limiting, expiration,
revocation, and key rotation. SHA-256 hashed storage under output/api_keys/.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from models import ApiKeyCreate, ApiKeyResponse, ApiKeyRecord
from logging_config import get_logger

logger = get_logger(__name__)

KEY_DIR = Path("output/api_keys")
KEY_PREFIX = "sk-graphrag-"


class ApiKeyManager:
    """Create, list, revoke, rotate API keys for external integrations."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or KEY_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key_id: str) -> Path:
        return self.base_dir / f"{key_id}.json"

    def _hash(self, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _generate_key(self) -> tuple[str, str, str]:
        """Returns (key_id, key_prefix, full_key)."""
        key_id = secrets.token_hex(8)
        raw = secrets.token_hex(24)
        full = f"{KEY_PREFIX}{raw}"
        return key_id, KEY_PREFIX, full

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── CRUD ──────────────────────────────────────────────────────────

    def create(self, data: ApiKeyCreate, created_by: str = "admin") -> ApiKeyResponse:
        key_id, prefix, full_key = self._generate_key()
        rec = ApiKeyRecord(
            key_id=key_id,
            name=data.name,
            key_prefix=prefix,
            key_hash=self._hash(full_key),
            created_by=created_by,
            created_at=self._now(),
            expires_at=data.expires_at,
            scopes=data.scopes,
            rate_limit_per_minute=data.rate_limit_per_minute,
        )
        self._save(rec)

        # Audit
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().api_key_created(created_by, key_id, data.name)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass

        logger.info("api_key_created", key_id=key_id, name=data.name)
        return ApiKeyResponse(
            key_id=key_id,
            name=data.name,
            key_prefix=prefix,
            full_key=full_key,
            created_at=rec.created_at,
            expires_at=rec.expires_at,
            scopes=data.scopes,
        )

    def list_all(self) -> list[ApiKeyRecord]:
        results = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                rec = ApiKeyRecord(**json.loads(f.read_text(encoding="utf-8")))
                results.append(rec)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def get(self, key_id: str) -> ApiKeyRecord | None:
        p = self._path(key_id)
        if not p.exists():
            return None
        try:
            return ApiKeyRecord(**json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def revoke(self, key_id: str, revoked_by: str = "admin") -> bool:
        rec = self.get(key_id)
        if not rec:
            return False
        rec.revoked = True
        self._save(rec)

        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().api_key_revoked(revoked_by, key_id)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass

        logger.info("api_key_revoked", key_id=key_id)
        return True

    def rotate(self, key_id: str, rotated_by: str = "admin") -> ApiKeyResponse | None:
        rec = self.get(key_id)
        if not rec:
            return None
        # Revoke old
        rec.revoked = True
        self._save(rec)
        # Create new with same scopes
        new_data = ApiKeyCreate(
            name=rec.name,
            expires_at=rec.expires_at,
            scopes=rec.scopes,
            rate_limit_per_minute=rec.rate_limit_per_minute,
        )
        return self.create(new_data, created_by=rotated_by)

    def validate(self, raw_key: str) -> ApiKeyRecord | None:
        """Validate a raw API key. Returns record if valid, None otherwise."""
        if not raw_key.startswith(KEY_PREFIX):
            return None
        h = self._hash(raw_key)
        now = datetime.now(timezone.utc)
        for f in self.base_dir.glob("*.json"):
            try:
                rec = ApiKeyRecord(**json.loads(f.read_text(encoding="utf-8")))
                if rec.key_hash == h and not rec.revoked:
                    if rec.expires_at:
                        exp = datetime.fromisoformat(rec.expires_at.replace("Z", "+00:00"))
                        if now > exp:
                            return None
                    rec.last_used_at = self._now()
                    self._save(rec)
                    return rec
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return None

    def delete(self, key_id: str) -> bool:
        p = self._path(key_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def _save(self, rec: ApiKeyRecord) -> None:
        self._path(rec.key_id).write_text(rec.model_dump_json(indent=2), encoding="utf-8")


# ── singleton ─────────────────────────────────────────────────────────────

_manager: ApiKeyManager | None = None


def get_api_key_manager() -> ApiKeyManager:
    global _manager
    if _manager is None:
        _manager = ApiKeyManager()
    return _manager
