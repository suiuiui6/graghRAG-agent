"""Local persistence behaviors; webhook HTTP is explicitly doubled, never live."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import os
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import DeliveryLog, FeedbackCreate, FeedbackUpdate, WebhookCreate, WebhookEvent
from services import audit_logger, backup, event_bus, feedback_store, webhook_manager


@pytest.fixture(autouse=True)
def local_services(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    root = tmp_path / "output"
    monkeypatch.setattr(event_bus, "EVENTS_DIR", root / "events")
    manager = webhook_manager.WebhookManager(root / "webhooks")
    bus = event_bus.EventBus()
    audit = audit_logger.AuditLogger(root / "audit")
    monkeypatch.setattr(webhook_manager, "_manager", manager)
    monkeypatch.setattr(event_bus, "_bus", bus)
    monkeypatch.setattr(audit_logger, "get_audit_logger", lambda: audit)
    store = feedback_store.FeedbackStore(root / "feedback")
    monkeypatch.setattr(feedback_store, "_store", store)
    monkeypatch.setattr(backup, "BACKUP_MANIFEST", {
        "kg": {"path": str(root / "kg"), "strategy": "incremental_version"},
        "feedback": {"path": str(root / "feedback"), "strategy": "full"},
        "docs_store": {"path": str(root / "docs_store.json"), "strategy": "full"},
        "logs": {"path": str(root / "logs"), "strategy": "rotate_only"},
        "cache": {"path": str(root / "cache"), "strategy": "skip"},
        "missing": {"path": str(root / "missing"), "strategy": "full"},
    })
    backups = backup.BackupManager(root / "backups")
    monkeypatch.setattr(backup, "_manager", backups)
    import requests
    import httpx

    def deny_requests(*args, **kwargs):
        raise AssertionError("Unstubbed external request is forbidden")

    async def deny_httpx(*args, **kwargs):
        raise AssertionError("Unstubbed external request is forbidden")

    monkeypatch.setattr(requests.sessions.Session, "request", deny_requests)
    monkeypatch.setattr(httpx.AsyncClient, "request", deny_httpx)
    return SimpleNamespace(root=root, manager=manager, bus=bus, audit=audit, store=store, backups=backups)


def _hook(services, *, secret="test-placeholder", events=None):
    return services.manager.create(WebhookCreate(url="https://example.invalid/webhook", events=events or ["doc.ingested"], secret=secret))


def _delivery(webhook_id, index, status="success"):
    return DeliveryLog(delivery_id=f"delivery-{index}", webhook_id=webhook_id, event_id=f"event-{index}", status=status, attempt=index + 1, timestamp=f"2026-10-12T00:00:0{index}+00:00")


def test_feedback_reload_status_history_filters_stats_and_delete(local_services):
    services = local_services
    positive = services.store.submit(FeedbackCreate(query_id="query-positive", rating="positive", user_id="用户甲"), query_text="问题甲", answer_text="答案甲")
    negative = services.store.submit(FeedbackCreate(query_id="query-negative", rating="negative", correction="更正", chunks_cited=["chunk-1"]), query_text="问题乙", answer_text="答案乙")
    reloaded = feedback_store.FeedbackStore(services.store.base_dir)
    assert reloaded.get(positive.feedback_id).query_text == "问题甲"
    assert reloaded.get(negative.feedback_id).chunks_cited == ["chunk-1"]
    assert reloaded.update(negative.feedback_id, FeedbackUpdate(status="acknowledged")).status == "acknowledged"
    assert reloaded.update(negative.feedback_id, FeedbackUpdate(status="resolved")).status == "resolved"
    assert [record.feedback_id for record in reloaded.list_all(status="resolved")] == [negative.feedback_id]
    assert reloaded.list_all(status="unknown") == []
    assert len(reloaded.list_all(limit=1)) == 1
    (reloaded.base_dir / "corrupt.json").write_text("broken JSON", encoding="utf-8")
    stats = reloaded.stats()
    assert (stats["total"], stats["positive"], stats["negative"], stats["positive_ratio"]) == (2, 1, 1, 0.5)
    assert stats["by_status"] == {"open": 1, "acknowledged": 0, "resolved": 1}
    assert stats["recent_negative"][0]["feedback_id"] == negative.feedback_id
    assert len(reloaded.list_all()) == 2
    assert reloaded.delete(negative.feedback_id) is True
    assert reloaded.delete(negative.feedback_id) is False
    assert reloaded.get("absent") is None
    assert reloaded.update("absent", FeedbackUpdate(status="resolved")) is None
    assert reloaded.update(positive.feedback_id, FeedbackUpdate()).status == "open"
    assert [record["event"] for record in services.audit.query()].count("feedback.resolved") == 1
    event_records = [json.loads(line) for path in (services.root / "events").glob("*.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
    assert [record["event_type"] for record in event_records] == ["feedback.received", "feedback.received", "feedback.resolved"]


def test_feedback_negative_history_is_bounded_and_ordered(local_services):
    store = local_services.store
    records = [store.submit(FeedbackCreate(rating="negative", comment=f"反馈{index}")) for index in range(12)]
    for index, record in enumerate(records):
        os.utime(store._path(record.feedback_id), (1000 + index, 1000 + index))
    stats = store.stats()
    assert stats["total"] == stats["negative"] == 12
    assert len(stats["recent_negative"]) == 10
    assert [item["feedback_id"] for item in stats["recent_negative"]] == [record.feedback_id for record in reversed(records[2:])]
    assert feedback_store.FeedbackStore(store.base_dir / "empty").stats()["positive_ratio"] == 0


@pytest.mark.parametrize("phase", ["submit", "resolved"])
def test_feedback_optional_publish_and_audit_failure_does_not_lose_record(monkeypatch, local_services, phase):
    def fail():
        raise OSError("optional observer unavailable")
    record = local_services.store.submit(FeedbackCreate(rating="positive")) if phase == "resolved" else None
    monkeypatch.setattr(event_bus, "get_event_bus", fail)
    monkeypatch.setattr(audit_logger, "get_audit_logger", fail)
    if phase == "submit":
        record = local_services.store.submit(FeedbackCreate(rating="negative"))
        expected = "open"
    else:
        local_services.store.update(record.feedback_id, FeedbackUpdate(status="resolved"))
        expected = "resolved"
    assert feedback_store.FeedbackStore(local_services.store.base_dir).get(record.feedback_id).status == expected


@pytest.mark.parametrize("comment", ["处理后的备注", ""])
def test_feedback_update_comment_is_persisted(local_services, comment):
    record = local_services.store.submit(FeedbackCreate(rating="negative", comment="原备注"))
    local_services.store.update(record.feedback_id, FeedbackUpdate(comment=comment))
    assert feedback_store.FeedbackStore(local_services.store.base_dir).get(record.feedback_id).comment == comment


def test_webhook_crud_soft_delete_and_delivery_counters_survive_reload(local_services):
    manager = local_services.manager
    record = _hook(local_services)
    manager.record_delivery(record.webhook_id, _delivery(record.webhook_id, 0, "failed"))
    manager.record_delivery(record.webhook_id, _delivery(record.webhook_id, 1))
    reloaded = webhook_manager.WebhookManager(manager.base_dir)
    saved = reloaded.get(record.webhook_id)
    assert (saved.delivery_count, saved.failed_count, saved.last_delivery_at) == (2, 1, "2026-10-12T00:00:01+00:00")
    assert [entry.delivery_id for entry in reloaded.get_deliveries(record.webhook_id, limit=1)] == ["delivery-1"]
    assert reloaded.update(record.webhook_id, WebhookCreate(url="https://example.invalid/updated", events=["*"], description="更新说明")).description == "更新说明"
    assert len(reloaded.get_matching("feedback.received")) == 1
    assert reloaded.delete(record.webhook_id)
    payload = json.loads(reloaded._path(record.webhook_id).read_text(encoding="utf-8"))
    assert payload["enabled"] is False and payload["deleted_at"]
    assert reloaded.get(record.webhook_id) is None and reloaded.list_all() == []
    assert reloaded.get_deliveries(record.webhook_id) == []
    assert reloaded.delete("absent") is True
    assert reloaded.update("absent", WebhookCreate(url="https://example.invalid/a", events=[])) is None


def test_webhook_matching_excludes_disabled_corrupt_deleted_and_unrelated(local_services):
    manager = local_services.manager
    exact = _hook(local_services)
    wildcard = _hook(local_services, events=["*"])
    unrelated = _hook(local_services, events=["feedback.received"])
    disabled = _hook(local_services)
    disabled.enabled = False
    manager._save(disabled)
    deleted = _hook(local_services)
    manager.delete(deleted.webhook_id)
    (manager.base_dir / "corrupt.json").write_text("bad", encoding="utf-8")
    (manager.base_dir / "schema-invalid.json").write_text("{}", encoding="utf-8")
    (manager.base_dir / "ignored_deliveries.json").write_text("{}", encoding="utf-8")
    assert {item["webhook_id"] for item in manager.get_matching("doc.ingested")} == {exact.webhook_id, wildcard.webhook_id}
    assert manager.get("corrupt") is None and manager.get("schema-invalid") is None
    assert len(manager.list_all()) == 4


def test_webhook_history_skips_corrupt_line_without_losing_older_deliveries(local_services):
    record = _hook(local_services)
    manager = local_services.manager
    manager.record_delivery(record.webhook_id, _delivery(record.webhook_id, 0))
    with manager._deliveries_path(record.webhook_id).open("a", encoding="utf-8") as handle:
        handle.write("bad JSON\n")
    manager.record_delivery(record.webhook_id, _delivery(record.webhook_id, 1))
    assert [item.delivery_id for item in manager.get_deliveries(record.webhook_id)] == ["delivery-1", "delivery-0"]


@pytest.mark.parametrize("secret,status", [("test-placeholder", 200), (None, 503)])
def test_webhook_ping_signs_exact_bytes_and_bounds_response(monkeypatch, local_services, secret, status):
    import requests
    record = _hook(local_services, secret=secret)
    captured = {}
    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return SimpleNamespace(ok=status == 200, status_code=status, text="reply" * 200)
    monkeypatch.setattr(requests, "post", post)
    result = local_services.manager.test_ping(record.webhook_id)
    assert result == {"status": "ok" if status == 200 else "failed", "http_status": status, "response": ("reply" * 200)[:500]}
    assert captured["url"] == record.url and captured["timeout"] == 10
    payload = json.loads(captured["data"])
    assert payload["event_type"] == "test.ping"
    if secret:
        expected = hmac.new(secret.encode(), captured["data"], hashlib.sha256).hexdigest()
        assert captured["headers"]["X-GraphRAG-Signature"] == f"sha256={expected}"
    else:
        assert "X-GraphRAG-Signature" not in captured["headers"]


def test_webhook_ping_missing_and_network_failure_return_explicit_error(monkeypatch, local_services):
    import requests
    assert local_services.manager.test_ping("absent") == {"status": "error", "message": "Webhook not found"}
    record = _hook(local_services)
    def fail(*args, **kwargs):
        raise requests.Timeout("x" * 300)
    monkeypatch.setattr(requests, "post", fail)
    assert local_services.manager.test_ping(record.webhook_id) == {"status": "error", "message": "x" * 200}


@pytest.mark.parametrize("responses,expected_attempts,expected_statuses", [
    ([503, 204], 2, ["failed", "success"]),
    ([OSError("temporary network fault"), 200], 2, ["failed", "success"]),
    ([503, 503, 503, 503], 4, ["failed"] * 4),
])
def test_event_delivery_retry_signature_backoff_and_persisted_history(monkeypatch, local_services, responses, expected_attempts, expected_statuses):
    import httpx
    record = _hook(local_services)
    queue = iter(responses)
    calls, sleeps = [], []
    class ClientBoundary:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 10}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            value = next(queue)
            if isinstance(value, Exception):
                raise value
            return SimpleNamespace(status_code=value)
    async def sleep(delay):
        sleeps.append(delay)
    monkeypatch.setattr(httpx, "AsyncClient", ClientBoundary)
    monkeypatch.setattr(event_bus.asyncio, "sleep", sleep)
    event = WebhookEvent(event_id="event-signature", event_type="doc.ingested", timestamp="2026-10-12T00:00:00Z", data={"document": "设备"})
    asyncio.run(local_services.bus._deliver(event, record.model_dump()))
    assert len(calls) == expected_attempts
    assert sleeps == [1, 5, 25][:expected_attempts - 1]
    history = list(reversed(local_services.manager.get_deliveries(record.webhook_id)))
    assert [item.attempt for item in history] == list(range(1, expected_attempts + 1))
    assert [item.status for item in history] == expected_statuses
    assert local_services.manager.get(record.webhook_id).failed_count == expected_statuses.count("failed")
    for url, kwargs in calls:
        assert url == record.url
        assert kwargs["content"] == event.model_dump_json().encode("utf-8")
        expected_signature = hmac.new(record.secret.encode(), kwargs["content"], hashlib.sha256).hexdigest()
        assert kwargs["headers"]["X-GraphRAG-Signature"] == f"sha256={expected_signature}"
        assert kwargs["headers"]["X-GraphRAG-Event-ID"] == event.event_id


def test_event_publish_persists_event_even_if_subscription_lookup_fails(monkeypatch, local_services):
    def fail(event_type):
        raise OSError("subscription store unavailable")
    monkeypatch.setattr(local_services.manager, "get_matching", fail)
    event = local_services.bus.publish("doc.ingested", {"doc_id": "doc-local"})
    paths = list((local_services.root / "events").glob("*.jsonl"))
    assert len(paths) == 1
    assert json.loads(paths[0].read_text(encoding="utf-8"))["event_id"] == event.event_id
    assert local_services.bus._queue.empty()


def test_event_publish_queue_full_keeps_existing_work_and_logs_new_event(local_services):
    record = _hook(local_services)
    local_services.bus._queue = asyncio.Queue(maxsize=1)
    first = local_services.bus.publish("doc.ingested", {"sequence": 1})
    second = local_services.bus.publish("doc.ingested", {"sequence": 2})
    queued_event, config = local_services.bus._queue.get_nowait()
    assert queued_event.event_id == first.event_id and config["webhook_id"] == record.webhook_id
    records = [json.loads(line) for path in (local_services.root / "events").glob("*.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
    assert [item["event_id"] for item in records] == [first.event_id, second.event_id]


def test_event_worker_continues_after_handler_failure_and_completes_queue(monkeypatch, local_services):
    async def run():
        bus = local_services.bus
        processed = []
        second_completed = asyncio.Event()
        async def deliver(event, config):
            processed.append(event.event_id)
            if len(processed) == 1:
                raise OSError("first subscription failed unexpectedly")
            second_completed.set()
        monkeypatch.setattr(bus, "_deliver", deliver)
        for number in range(2):
            await bus._queue.put((WebhookEvent(event_id=f"event-{number}", event_type="doc.ingested", timestamp="2026-10-12T00:00:00Z", data={}), {}))
        await bus.start()
        try:
            await asyncio.wait_for(second_completed.wait(), timeout=1)
            assert processed == ["event-0", "event-1"]
            await asyncio.wait_for(bus._queue.join(), timeout=0.1)
        finally:
            await bus.stop()
        assert bus._worker_task.done()
    asyncio.run(run())


@pytest.mark.parametrize("in_flight", [False, True])
def test_event_worker_stop_releases_only_acquired_queue_work(monkeypatch, local_services, in_flight):
    async def run():
        bus = local_services.bus
        entered = asyncio.Event()
        async def deliver(event, config):
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(bus, "_deliver", deliver)
        if in_flight:
            await bus._queue.put((WebhookEvent(event_id="cancel-event", event_type="doc.ingested", timestamp="2026-10-12T00:00:00Z", data={}), {}))
        await bus.start()
        if in_flight:
            await asyncio.wait_for(entered.wait(), timeout=1)
        else:
            # Let the worker block in queue.get before cancellation.
            await asyncio.sleep(0)
        await bus.stop()
        await asyncio.wait_for(bus._queue.join(), timeout=0.1)
        assert bus._worker_task.done()
        assert bus._worker_task.exception() is None
    asyncio.run(run())


def _seed_backup(services):
    root = services.root
    active = root / "kg/doc_alpha/v2"
    active.mkdir(parents=True)
    (active / "nodes.json").write_text('{"nodes":[{"label":"设备"}]}', encoding="utf-8")
    (root / "kg/doc_alpha/versions.json").write_text('{"active_version":2}', encoding="utf-8")
    inactive = root / "kg/doc_alpha/v1"
    inactive.mkdir()
    (inactive / "nodes.json").write_text("inactive", encoding="utf-8")
    (root / "kg/not-a-document").mkdir()
    (root / "kg/ignored.txt").write_text("ignored", encoding="utf-8")
    (root / "docs_store.json").write_text('[{"document_id":"doc_alpha"}]', encoding="utf-8")
    (root / "logs").mkdir()
    (root / "logs/app.log").write_text("not backed up", encoding="utf-8")
    (root / "cache").mkdir()
    (root / "cache/data.json").write_text("not backed up", encoding="utf-8")
    services.store.submit(FeedbackCreate(rating="positive"))
    return active


def test_backup_archive_active_version_manifest_restore_and_pre_restore_snapshot(local_services):
    services = local_services
    active = _seed_backup(services)
    result = services.backups.create_backup()
    assert result.status == "completed"
    archive = services.backups.base_dir / f"{result.backup_id}.tar.gz"
    assert result.manifest.checksum == hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
    with tarfile.open(archive) as handle:
        names = handle.getnames()
    assert f"{result.backup_id}/kg/doc_alpha/v2/nodes.json" in names
    assert not any("v1" in name or "/logs" in name or "/cache" in name for name in names)
    manifest = services.backups.get_manifest(result.backup_id)
    assert manifest["directories"] == ["kg", "feedback", "docs_store"]
    assert services.backups.verify(result.backup_id)["valid"] is True
    assert services.backups.verify(result.backup_id)["has_kg"] is True
    (active / "nodes.json").write_text("changed after backup", encoding="utf-8")
    (services.root / "docs_store.json").write_text("changed docs", encoding="utf-8")
    restored = services.backups.restore(result.backup_id)
    assert restored.status == "completed"
    assert json.loads((active / "nodes.json").read_text(encoding="utf-8"))["nodes"][0]["label"] == "设备"
    snapshot = services.backups.base_dir / restored.pre_restore_snapshot
    assert (snapshot / "kg/doc_alpha/v2/nodes.json").read_text(encoding="utf-8") == "changed after backup"
    assert (snapshot / "docs_store").read_text(encoding="utf-8") == "changed docs"
    assert not (services.backups.base_dir / result.backup_id).exists()
    assert services.backups.list_backups()[0]["backup_id"] == result.backup_id


@pytest.mark.parametrize("name,link", [("../../escaped.txt", None), ("malicious/link", "../../outside")])
def test_backup_restore_rejects_archive_traversal_and_external_symlink(local_services, name, link):
    manager = local_services.backups
    with tarfile.open(manager.base_dir / "malicious.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo(name)
        if link:
            info.type = tarfile.SYMTYPE
            info.linkname = link
            archive.addfile(info)
        else:
            content = b"attacker content"
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    result = manager.restore("malicious")
    assert result.status == "failed" and result.error
    assert not (local_services.root.parent / "escaped.txt").exists()
    assert not (manager.base_dir / "malicious/link").exists()


def test_backup_missing_corrupt_and_missing_manifest_have_explicit_results(local_services):
    manager = local_services.backups
    assert manager.restore("absent").error == "Backup not found"
    assert manager.verify("absent")["valid"] is False
    assert manager.get_manifest("absent") is None
    (manager.base_dir / "corrupt.tar.gz").write_bytes(b"not a gzip archive")
    assert manager.restore("corrupt").status == "failed"
    assert manager.verify("corrupt")["valid"] is False
    assert manager.get_manifest("corrupt") is None
    with tarfile.open(manager.base_dir / "empty.tar.gz", "w:gz"):
        pass
    assert manager.verify("empty")["valid"] is False
    assert manager.get_manifest("empty") is None


def test_backup_corrupt_version_metadata_returns_failure_and_removes_staging(local_services):
    active = _seed_backup(local_services)
    (active.parent / "versions.json").write_text("invalid JSON", encoding="utf-8")
    result = local_services.backups.create_backup()
    assert result.status == "failed" and result.error
    assert not (local_services.backups.base_dir / result.backup_id).exists()
    assert local_services.backups.list_backups() == []


def test_backup_retention_keeps_manual_and_newest_daily_weekly_files(local_services):
    manager = local_services.backups
    names = ["daily_old", "daily_new", "weekly_old", "weekly_new", "manual_old", "legacy_old"]
    for index, name in enumerate(names):
        path = manager.base_dir / f"{name}.tar.gz"
        path.write_bytes(b"retention fixture")
        os.utime(path, (1000 + index, 1000 + index))
    assert manager.cleanup_old_backups(keep_daily=1, keep_weekly=1) == 3
    assert {path.name for path in manager.base_dir.glob("*.tar.gz")} == {"legacy_old.tar.gz", "weekly_new.tar.gz", "manual_old.tar.gz"}


@pytest.mark.parametrize("exception_type", [PermissionError, OSError])
def test_backup_cleanup_failure_is_optional_or_required_as_requested(monkeypatch, local_services, exception_type):
    manager = local_services.backups
    target = manager.base_dir / "staging"
    target.mkdir()
    def fail(path):
        assert Path(path) == target
        raise exception_type("file locked")
    with monkeypatch.context() as scoped:
        scoped.setattr(backup.shutil, "rmtree", fail)
        assert manager._cleanup_directory(target, required=False) is False
        with pytest.raises(exception_type, match="file locked"):
            manager._cleanup_directory(target, required=True)
    assert manager._cleanup_directory(target, required=True) is True
    assert manager._cleanup_directory(target, required=True) is True


def test_backup_scheduled_run_creates_daily_archive(local_services):
    _seed_backup(local_services)
    result = local_services.backups.scheduled_backup()
    assert result.status == "completed" and result.backup_id.startswith("daily_")
    assert local_services.backups.verify(result.backup_id)["manifest"]["backup_type"] == "daily"
