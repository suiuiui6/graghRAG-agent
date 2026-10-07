"""
Tenant Service — §7.1 of enterprise-evolution-blueprint.

Organization and Project CRUD with member management.
Data stored as JSON files under output/tenants/.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import Organization, OrganizationCreate, Project, ProjectCreate, OrgMembership, MemberInvite
from logging_config import get_logger

logger = get_logger(__name__)

TENANTS_DIR = Path("output/tenants")
ORGS_DIR = TENANTS_DIR / "orgs"
PROJECTS_DIR = TENANTS_DIR / "projects"
MEMBERS_DIR = TENANTS_DIR / "members"

DEFAULT_ORG_ID = os.getenv("DEFAULT_ORG_ID", "default")


class TenantService:
    """Organization, Project, and Member management."""

    def __init__(self, base_dir: Path | None = None):
        d = base_dir or TENANTS_DIR
        (d / "orgs").mkdir(parents=True, exist_ok=True)
        (d / "projects").mkdir(parents=True, exist_ok=True)
        (d / "members").mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _member_entries(self):
        for f in sorted(MEMBERS_DIR.glob("*.json")):
            payload = self._load_json(f)
            if payload is None:
                continue
            yield f, payload

    def _is_removed_member_payload(self, payload: dict | None) -> bool:
        return bool(payload and payload.get("removed_at"))

    def _find_member_entry(self, org_id: str, user_id: str) -> tuple[Path, dict] | None:
        for f, payload in self._member_entries():
            if self._is_removed_member_payload(payload):
                continue
            if payload.get("org_id") == org_id and payload.get("user_id") == user_id:
                return f, payload
        return None

    # ── Organization CRUD ──────────────────────────────────────────────

    def create_org(self, data: OrganizationCreate) -> Organization:
        org_id = uuid4().hex[:12]
        org = Organization(
            org_id=org_id,
            name=data.name,
            slug=data.slug,
            contact_email=data.contact_email,
            created_at=self._now(),
        )
        self._save_org(org)
        logger.info("org_created", org_id=org_id, name=data.name)
        return org

    def get_org(self, org_id: str) -> Organization | None:
        p = ORGS_DIR / f"{org_id}.json"
        payload = self._load_json(p)
        if payload is None or not payload.get("is_active", True):
            return None
        return Organization(**payload)

    def list_orgs(self) -> list[Organization]:
        results = []
        for f in sorted(ORGS_DIR.glob("*.json")):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
                if not payload.get("is_active", True):
                    continue
                results.append(Organization(**payload))
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def update_org(self, org_id: str, updates: dict) -> Organization | None:
        p = ORGS_DIR / f"{org_id}.json"
        payload = self._load_json(p)
        if payload is None or not payload.get("is_active", True):
            return None
        org = Organization(**payload)
        for key in ("name", "slug", "contact_email", "plan", "is_active"):
            if key in updates:
                setattr(org, key, updates[key])
        org.updated_at = self._now()
        self._save_org(org)
        return org

    def delete_org(self, org_id: str) -> bool:
        p = ORGS_DIR / f"{org_id}.json"
        payload = self._load_json(p)
        if payload is None:
            return False
        if not payload.get("is_active", True):
            return True
        payload["is_active"] = False
        payload["updated_at"] = self._now()
        payload["deleted_at"] = payload["updated_at"]
        self._write_json(p, payload)
        return True

    def _save_org(self, org: Organization) -> None:
        (ORGS_DIR / f"{org.org_id}.json").write_text(
            org.model_dump_json(indent=2), encoding="utf-8")

    # ── Project CRUD ────────────────────────────────────────────────────

    def create_project(self, org_id: str, data: ProjectCreate, created_by: str) -> Project | None:
        org = self.get_org(org_id)
        if not org:
            return None
        project_id = uuid4().hex[:12]
        proj = Project(
            project_id=project_id,
            org_id=org_id,
            name=data.name,
            description=data.description,
            project_code=data.project_code,
            created_by=created_by,
            created_at=self._now(),
        )
        self._save_project(proj)
        logger.info("project_created", project_id=project_id, org_id=org_id, name=data.name)
        return proj

    def get_project(self, project_id: str) -> Project | None:
        p = PROJECTS_DIR / f"{project_id}.json"
        if not p.exists():
            return None
        return Project(**json.loads(p.read_text(encoding="utf-8")))

    def list_projects(self, org_id: str | None = None) -> list[Project]:
        results = []
        for f in sorted(PROJECTS_DIR.glob("*.json")):
            try:
                proj = Project(**json.loads(f.read_text(encoding="utf-8")))
                if org_id and proj.org_id != org_id:
                    continue
                results.append(proj)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def update_project(self, project_id: str, updates: dict) -> Project | None:
        proj = self.get_project(project_id)
        if not proj:
            return None
        for key in ("name", "description", "project_code", "is_archived"):
            if key in updates:
                setattr(proj, key, updates[key])
        proj.updated_at = self._now()
        self._save_project(proj)
        return proj

    def archive_project(self, project_id: str) -> Project | None:
        return self.update_project(project_id, {"is_archived": True})

    def delete_project(self, project_id: str) -> bool:
        p = PROJECTS_DIR / f"{project_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    def _save_project(self, proj: Project) -> None:
        (PROJECTS_DIR / f"{proj.project_id}.json").write_text(
            proj.model_dump_json(indent=2), encoding="utf-8")

    # ── Member Management ───────────────────────────────────────────────

    def add_member(self, org_id: str, invite: MemberInvite, invited_by: str | None = None) -> OrgMembership | None:
        org = self.get_org(org_id)
        if not org:
            return None
        existing = self.get_member(org_id, invite.user_id)
        if existing:
            return existing
        mid = uuid4().hex[:12]
        member = OrgMembership(
            membership_id=mid,
            org_id=org_id,
            user_id=invite.user_id,
            role=invite.role,
            joined_at=self._now(),
            invited_by=invited_by,
        )
        self._save_member(member)
        logger.info("member_added", org_id=org_id, user_id=invite.user_id, role=invite.role)
        return member

    def list_members(self, org_id: str) -> list[OrgMembership]:
        results = []
        for _path, payload in self._member_entries():
            try:
                if self._is_removed_member_payload(payload):
                    continue
                m = OrgMembership(**payload)
                if m.org_id == org_id:
                    results.append(m)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def get_member(self, org_id: str, user_id: str) -> OrgMembership | None:
        entry = self._find_member_entry(org_id, user_id)
        if entry is None:
            return None
        _path, payload = entry
        return OrgMembership(**payload)

    def update_member_role(self, org_id: str, user_id: str, role: str) -> OrgMembership | None:
        entry = self._find_member_entry(org_id, user_id)
        if entry is None:
            return None
        path, payload = entry
        payload["role"] = role
        payload["updated_at"] = self._now()
        self._write_json(path, payload)
        logger.info("member_role_updated", org_id=org_id, user_id=user_id, role=role)
        return OrgMembership(**payload)

    def remove_member(self, org_id: str, user_id: str) -> bool:
        entry = self._find_member_entry(org_id, user_id)
        if entry is None:
            return False
        path, payload = entry
        payload["removed_at"] = self._now()
        payload["updated_at"] = payload["removed_at"]
        self._write_json(path, payload)
        logger.info("member_removed", org_id=org_id, user_id=user_id)
        return True

    def _save_member(self, member: OrgMembership) -> None:
        key = f"{member.org_id}_{member.user_id}_{member.membership_id}"
        (MEMBERS_DIR / f"{key}.json").write_text(
            member.model_dump_json(indent=2), encoding="utf-8")

    # ── Tenant Context Helper ──────────────────────────────────────────

    def get_user_orgs(self, user_id: str) -> list[dict]:
        """List orgs the user belongs to, with roles."""
        orgs = []
        seen = set()
        for _path, payload in self._member_entries():
            try:
                if self._is_removed_member_payload(payload):
                    continue
                m = OrgMembership(**payload)
                if m.user_id == user_id and m.org_id not in seen:
                    org = self.get_org(m.org_id)
                    if org:
                        orgs.append({"org_id": m.org_id, "name": org.name, "role": m.role})
                        seen.add(m.org_id)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        if not orgs:
            orgs = [{"org_id": DEFAULT_ORG_ID, "name": "Default", "role": "org_admin"}]
        return orgs


_service: TenantService | None = None


def get_tenant_service() -> TenantService:
    global _service
    if _service is None:
        _service = TenantService()
    return _service
