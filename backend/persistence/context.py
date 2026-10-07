"""Persistence access scopes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Authenticated scope used for tenant-owned persistence access."""

    owner_id: str
    tenant_id: str
    org_id: str
    project_id: str

    def __post_init__(self) -> None:
        for field_name in ("owner_id", "tenant_id", "org_id", "project_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SystemContext:
    """Explicit scope for system maintenance without a user owner."""

    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")


def context_from_request(request: Any) -> AccessContext:
    """Convert the middleware tenant wire shape into an access context."""
    tenant = getattr(getattr(request, "state", None), "tenant", None)
    if not isinstance(tenant, dict):
        raise ValueError("owner_id is required in the request tenant context")

    user_id = tenant.get("user_id")
    legacy_owner_id = tenant.get("owner_id")
    org_id = tenant.get("org_id")
    project_id = tenant.get("project_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("owner_id requires a non-empty user_id")
    if legacy_owner_id is not None and legacy_owner_id != user_id:
        raise ValueError("owner_id conflicts with user_id")
    if not isinstance(org_id, str) or not org_id.strip():
        raise ValueError("org_id must be a non-empty string")
    if project_id is None:
        project_id = "default"
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id must be a non-empty string")

    return AccessContext(
        owner_id=user_id,
        tenant_id=f"{org_id}/{project_id}",
        org_id=org_id,
        project_id=project_id,
    )


def legacy_context() -> AccessContext:
    """Return the compatibility scope for pre-tenant persistence data."""
    return AccessContext(
        owner_id="legacy",
        tenant_id="default/default",
        org_id="default",
        project_id="default",
    )
