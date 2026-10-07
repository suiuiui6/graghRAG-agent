"""
Phase 3 Integration Tests — §6.1-6.7 of enterprise-evolution-blueprint.

Tests auth (JWT), audit, API keys, webhooks, bot handler, health checker.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_output(sandbox_tmp_path):
    """Temp output directory with minimal data for audit/api_keys/webhooks."""
    base = sandbox_tmp_path
    (base / "output").mkdir()
    old_cwd = os.getcwd()
    os.chdir(base)
    try:
        yield base
    finally:
        os.chdir(old_cwd)


# ── JWT Tests (§6.1) ──────────────────────────────────────────────────

class TestJwtMiddleware:
    def test_create_access_token(self):
        from middleware.jwt_middleware import create_access_token, decode_token
        token = create_access_token("user1", "testuser", "test@local",
                                    roles=["editor"])
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user1"
        assert payload["preferred_username"] == "testuser"
        assert "editor" in payload["roles"]

    def test_decode_invalid_token(self):
        from middleware.jwt_middleware import decode_token
        assert decode_token("not.a.valid.jwt") is None

    def test_create_refresh_token(self):
        from middleware.jwt_middleware import create_refresh_token, decode_token
        token = create_refresh_token("user1")
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_token_expiry(self):
        from middleware.jwt_middleware import create_access_token, decode_token
        # Create token that is already expired (negative expiry)
        # We test that an expired token cannot be decoded
        token = create_access_token("u1", "test", expires_minutes=-1)
        payload = decode_token(token)
        assert payload is None


# ── Audit Tests (§6.5) ────────────────────────────────────────────────

class TestAuditLogger:
    def test_log_write(self, temp_output):
        from services.audit_logger import AuditLogger
        audit = AuditLogger(base_dir=temp_output / "output" / "audit")
        audit.log("test.event", "testuser", ip="127.0.0.1", key="value")
        audit.auth_login("user1")
        audit.auth_logout("user1")

        results = audit.query()
        assert len(results) >= 3

    def test_query_filter(self, temp_output):
        from services.audit_logger import AuditLogger
        audit = AuditLogger(base_dir=temp_output / "output" / "audit")
        audit.log("user.login", "userA")
        audit.log("user.login", "userB")
        audit.log("data.exported", "userA", fmt="csv")

        results = audit.query(event="user.login")
        assert len(results) >= 2

        results = audit.query(user_id="userA")
        assert len(results) >= 2

    def test_export_csv(self, temp_output):
        from services.audit_logger import AuditLogger
        audit = AuditLogger(base_dir=temp_output / "output" / "audit")
        audit.log("test.event", "user1")
        csv_data = audit.export_csv()
        assert "test.event" in csv_data
        assert csv_data.startswith("﻿")  # UTF-8 BOM

    def test_convenience_methods(self, temp_output):
        from services.audit_logger import AuditLogger
        audit = AuditLogger(base_dir=temp_output / "output" / "audit")
        audit.auth_failed("hacker", "wrong password")
        audit.data_exported("admin", "neo4j", 100)
        audit.backup_triggered("admin", "bkp1", "manual")
        audit.api_key_created("admin", "key1", "test-key")
        audit.api_key_revoked("admin", "key1")
        results = audit.query()
        assert len(results) >= 5


# ── API Key Tests (§6.6) ─────────────────────────────────────────────

class TestApiKeyManager:
    def test_create_and_validate(self, temp_output):
        from services.api_key_manager import ApiKeyManager
        from models import ApiKeyCreate
        mgr = ApiKeyManager(base_dir=temp_output / "output" / "api_keys")
        result = mgr.create(ApiKeyCreate(name="test-key", scopes=["read:query"]))
        assert result.full_key.startswith("sk-graphrag-")
        assert len(result.full_key) > 30

        # Validate
        rec = mgr.validate(result.full_key)
        assert rec is not None
        assert rec.name == "test-key"
        assert "read:query" in rec.scopes

    def test_validate_invalid_key(self, temp_output):
        from services.api_key_manager import ApiKeyManager
        mgr = ApiKeyManager(base_dir=temp_output / "output" / "api_keys")
        assert mgr.validate("not-valid-key") is None
        assert mgr.validate("sk-graphrag-fake123") is None

    def test_revoke(self, temp_output):
        from services.api_key_manager import ApiKeyManager
        from models import ApiKeyCreate
        mgr = ApiKeyManager(base_dir=temp_output / "output" / "api_keys")
        result = mgr.create(ApiKeyCreate(name="temp-key"))
        assert mgr.revoke(result.key_id)
        assert mgr.validate(result.full_key) is None

    def test_rotate(self, temp_output):
        from services.api_key_manager import ApiKeyManager
        from models import ApiKeyCreate
        mgr = ApiKeyManager(base_dir=temp_output / "output" / "api_keys")
        result = mgr.create(ApiKeyCreate(name="rotate-key"))
        old_key = result.full_key
        new_result = mgr.rotate(result.key_id)
        assert new_result is not None
        assert new_result.full_key != old_key
        # Old key should be invalid
        assert mgr.validate(old_key) is None

    def test_list_all(self, temp_output):
        from services.api_key_manager import ApiKeyManager
        from models import ApiKeyCreate
        mgr = ApiKeyManager(base_dir=temp_output / "output" / "api_keys")
        mgr.create(ApiKeyCreate(name="key1"))
        mgr.create(ApiKeyCreate(name="key2"))
        keys = mgr.list_all()
        assert len(keys) >= 2


# ── Webhook Tests (§6.3) ─────────────────────────────────────────────

class TestWebhookManager:
    def test_create_webhook(self, temp_output):
        from services.webhook_manager import WebhookManager
        from models import WebhookCreate
        mgr = WebhookManager(base_dir=temp_output / "output" / "webhooks")
        rec = mgr.create(WebhookCreate(
            url="https://example.com/hook",
            events=["doc.ingested", "feedback.received"],
            secret="shared-secret",
        ))
        assert rec.webhook_id
        assert rec.enabled

    def test_get_matching(self, temp_output):
        from services.webhook_manager import WebhookManager
        from models import WebhookCreate
        mgr = WebhookManager(base_dir=temp_output / "output" / "webhooks")
        mgr.create(WebhookCreate(url="https://a.com/hook", events=["doc.ingested"]))
        mgr.create(WebhookCreate(url="https://b.com/hook", events=["feedback.received"]))
        mgr.create(WebhookCreate(url="https://c.com/hook", events=["*"]))

        matching = mgr.get_matching("doc.ingested")
        assert len(matching) >= 2  # doc.ingested + *

    def test_crud(self, temp_output):
        from services.webhook_manager import WebhookManager
        from models import WebhookCreate
        mgr = WebhookManager(base_dir=temp_output / "output" / "webhooks")
        rec = mgr.create(WebhookCreate(
            url="https://example.com/hook", events=["doc.ingested"]))
        assert mgr.get(rec.webhook_id) is not None

        updated = mgr.update(rec.webhook_id, WebhookCreate(
            url="https://new.example.com/hook", events=["*"]))
        assert updated is not None
        assert updated.url == "https://new.example.com/hook"

        mgr.delete(rec.webhook_id)
        assert mgr.get(rec.webhook_id) is None


# ── Card Builder Tests (§6.2) ────────────────────────────────────────

class TestCardBuilder:
    def test_feishu_qa_card(self):
        from services.card_builder import CardBuilder
        card = CardBuilder.feishu_qa_card(
            "预算执行率", "预算执行率84%",
            ["2025年项目中期报告 第12页"], query_id="q1")
        assert card["header"]["template"] == "blue"
        assert len(card["elements"]) >= 2

    def test_feishu_error_card(self):
        from services.card_builder import CardBuilder
        card = CardBuilder.feishu_error_card("测试错误")
        assert card["header"]["template"] == "red"

    def test_dingtalk_markdown(self):
        from services.card_builder import CardBuilder
        msg = CardBuilder.dingtalk_markdown("answer", ["source1"])
        assert msg["msgtype"] == "markdown"

    def test_wecom_markdown(self):
        from services.card_builder import CardBuilder
        msg = CardBuilder.wecom_markdown("answer", ["source1"])
        assert msg["msgtype"] == "markdown"


# ── Auth Service Tests (§6.1) ────────────────────────────────────────

class TestAuthService:
    def test_login_local(self, temp_output):
        from services.auth_service import AuthService
        svc = AuthService()
        # Override users dir
        import services.auth_service as a
        old_dir = a.USERS_DIR
        a.USERS_DIR = temp_output / "output" / "users"
        try:
            tokens = svc.login_local("testuser", "")
            assert tokens is not None
            assert tokens.access_token
            assert tokens.refresh_token
        finally:
            a.USERS_DIR = old_dir

    def test_token_refresh(self, temp_output):
        from services.auth_service import AuthService
        svc = AuthService()
        tokens = svc.login_local("refreshuser", "")
        assert tokens is not None
        new_tokens = svc.refresh_tokens(tokens.refresh_token)
        assert new_tokens is not None
        # Both new tokens should be valid
        from middleware.jwt_middleware import decode_token
        assert decode_token(new_tokens.access_token) is not None
        ref_payload = decode_token(new_tokens.refresh_token)
        assert ref_payload is not None
        assert ref_payload["type"] == "refresh"

    def test_list_users(self, temp_output):
        from services.auth_service import AuthService
        import services.auth_service as a
        old_dir = a.USERS_DIR
        a.USERS_DIR = temp_output / "output" / "users"
        try:
            svc = AuthService()
            svc.login_local("user1", "")
            svc.login_local("user2", "")
            users = svc.list_users()
            assert len(users) >= 2
        finally:
            a.USERS_DIR = old_dir


# ── Health Checker Tests (§6.7) ──────────────────────────────────────

class TestHealthChecker:
    def test_probe_all(self):
        from services.health_checker import HealthChecker
        hc = HealthChecker()
        results = hc.probe_all()
        assert "deepseek_api" in results
        assert "mineru_api" in results
        assert "chromadb" in results
        assert "oauth2_provider" in results
        assert "feishu_bot" in results
        for k, v in results.items():
            assert v["status"] in ("ok", "degraded", "down")


# ── Event Bus Tests (§6.3) ──────────────────────────────────────────

class TestEventBus:
    def test_publish_event(self, temp_output):
        from services.event_bus import EventBus
        bus = EventBus()
        bus._queue._queue.clear()  # Reset queue
        event = bus.publish("test.event", {"key": "value"})
        assert event.event_id
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}


# ── API Endpoint Tests ────────────────────────────────────────────────

class TestPhase3Endpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from server import app
        return TestClient(app)

    def test_auth_login_page(self, client):
        r = client.get("/api/v1/auth/login")
        assert r.status_code in (200, 401)

    def test_auth_login_local(self, client):
        r = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "", "provider": "local"
        })
        assert r.status_code in (200, 401)

    def test_bot_config(self, client):
        r = client.get("/api/v1/bot/config")
        assert r.status_code in (200, 401)

    def test_webhooks_list(self, client):
        r = client.get("/api/v1/webhooks")
        assert r.status_code in (200, 401)

    def test_audit_query(self, client):
        r = client.get("/api/v1/audit")
        assert r.status_code in (200, 401)

    def test_api_keys_list(self, client):
        r = client.get("/api/v1/api-keys")
        assert r.status_code in (200, 401)

    def test_health_probe_trigger(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
