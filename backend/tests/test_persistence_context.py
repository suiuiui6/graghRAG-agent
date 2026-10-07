from types import SimpleNamespace

import pytest

from models import TaskStatus
from persistence.context import AccessContext, SystemContext, context_from_request, legacy_context


def test_context_from_request_maps_default_tenant_scope() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={"org_id": "org-a", "project_id": None, "user_id": "user-a"}
        )
    )

    assert context_from_request(request) == AccessContext(
        owner_id="user-a",
        tenant_id="org-a/default",
        org_id="org-a",
        project_id="default",
    )


def test_context_from_request_maps_non_default_project_scope() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={
                "org_id": "org-a",
                "project_id": "project-a",
                "user_id": "user-a",
            }
        )
    )

    assert context_from_request(request) == AccessContext(
        owner_id="user-a",
        tenant_id="org-a/project-a",
        org_id="org-a",
        project_id="project-a",
    )


def test_context_from_request_requires_user_id_not_legacy_owner_id() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={"org_id": "org-a", "project_id": None, "owner_id": "user-a"}
        )
    )

    with pytest.raises(ValueError, match="owner_id"):
        context_from_request(request)


def test_context_from_request_rejects_conflicting_owner_id() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={
                "org_id": "org-a",
                "project_id": None,
                "user_id": "user-a",
                "owner_id": "user-b",
            }
        )
    )

    with pytest.raises(ValueError, match="owner_id"):
        context_from_request(request)


@pytest.mark.parametrize(
    ("tenant", "message_field"),
    [
        ({"org_id": "org-a", "project_id": None}, "owner_id"),
        ({"org_id": "org-a", "project_id": None, "user_id": ""}, "owner_id"),
        ({"org_id": "", "project_id": "project-a", "user_id": "user-a"}, "org_id"),
        ({"org_id": "org-a", "project_id": "", "user_id": "user-a"}, "project_id"),
    ],
)
def test_context_from_request_rejects_missing_owner_or_empty_scope(
    tenant: dict, message_field: str
) -> None:
    request = SimpleNamespace(state=SimpleNamespace(tenant=tenant))

    with pytest.raises(ValueError, match=message_field):
        context_from_request(request)


@pytest.mark.parametrize("field_name", ["owner_id", "tenant_id", "org_id", "project_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_access_context_rejects_empty_fields(field_name: str, value: str) -> None:
    fields = {
        "owner_id": "user-a",
        "tenant_id": "org-a/default",
        "org_id": "org-a",
        "project_id": "default",
    }
    fields[field_name] = value

    with pytest.raises(ValueError, match=field_name):
        AccessContext(**fields)


def test_system_context_is_independent_and_requires_reason() -> None:
    context = SystemContext(reason="startup reconciliation")

    assert isinstance(context, SystemContext)
    assert not isinstance(context, AccessContext)
    with pytest.raises(ValueError):
        SystemContext(reason="")


def test_legacy_context_uses_default_scope() -> None:
    assert legacy_context() == AccessContext(
        owner_id="legacy",
        tenant_id="default/default",
        org_id="default",
        project_id="default",
    )


def test_task_status_values_are_exactly_the_persistence_wire_values() -> None:
    assert {status.value for status in TaskStatus} == {
        "pending",
        "running",
        "done",
        "failed",
    }
