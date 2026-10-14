"""真实磁盘版本保留、回滚和并发协议回归。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kg_store import KgVersionManager
from services import lifecycle


@pytest.fixture
def versions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "kg"
    monkeypatch.setattr(lifecycle, "KG_DIR", root)
    manager = KgVersionManager("1", root)
    manager.doc_dir.mkdir(parents=True)
    for number in range(12):
        path = manager.doc_dir / f"v{number}"
        path.mkdir()
        (path / "nodes.json").write_text("[]")
        (path / "edges.json").write_text("[]")
    manager.versions_file.write_text(json.dumps({"active_version": 0, "versions": [
        {"version": number} for number in range(12)]}))
    return manager, lifecycle.DataLifecycleManager()


def test_active_zero_retained_and_consumers_consistent(versions):
    manager, cleanup = versions
    assert cleanup._find_expired_versions() == ["doc_1/v1", "doc_1/v2"]
    assert cleanup._clean_kg_versions() == 2
    assert {p.name for p in manager.doc_dir.glob("v[0-9]*")} == {"v0", *[f"v{i}" for i in range(3, 12)]}
    assert {entry["version"] for entry in manager.list_versions()} == {0, *range(3, 12)}
    assert not manager.activate_version(1)
    assert manager.create_version([], []) == 12


@pytest.mark.parametrize("metadata", [None, "broken", "[]", "{}", '{"active_version": 99}', '{"active_version": true}', '{"active_version": "0"}',
    '{"active_version": 0, "versions": []}', '{"active_version": -1, "versions": []}',
    '{"active_version": 0, "versions": [null]}', '{"active_version": 0, "versions": [{"version": true}]}'])
def test_unknown_active_fails_closed(versions, metadata):
    manager, cleanup = versions
    if metadata is None:
        manager.versions_file.unlink()
    else:
        manager.versions_file.write_text(metadata)
    assert cleanup._find_expired_versions() == []
    assert cleanup._clean_kg_versions() == 0
    assert len(list(manager.doc_dir.glob("v[0-9]*"))) == 12


def test_invalid_version_names_not_counted(versions):
    manager, cleanup = versions
    for name in ("vbad", "v-1", "v1.5", "v01"):
        (manager.doc_dir / name).mkdir()
    assert cleanup._find_expired_versions() == ["doc_1/v1", "doc_1/v2"]


def test_missing_directory_cannot_activate(versions):
    manager, _ = versions
    import shutil
    shutil.rmtree(manager.doc_dir / "v4")
    assert not manager.activate_version(4)
    assert manager.active_version() == 0


def test_manifest_replace_failure_restores_complete_directory(versions, monkeypatch):
    manager, cleanup = versions
    import kg_store
    original = manager.versions_file.read_bytes()
    replace = kg_store.os.replace
    def denied(source, destination):
        if Path(destination) == manager.versions_file:
            raise PermissionError("manifest commit denied")
        return replace(source, destination)
    monkeypatch.setattr(kg_store.os, "replace", denied)
    assert cleanup._clean_kg_versions() == 0
    assert manager.versions_file.read_bytes() == original
    assert (manager.doc_dir / "v1/nodes.json").read_text() == "[]"
    assert not list(manager.doc_dir.glob(".retired-*"))
    assert not list(manager.doc_dir.glob(".versions-*.tmp"))


def test_invalid_highwater_does_not_move_any_directory(versions):
    manager, cleanup = versions
    metadata = json.loads(manager.versions_file.read_text())
    metadata["next_version"] = "invalid"
    manager.versions_file.write_text(json.dumps(metadata))
    assert cleanup._clean_kg_versions() == 0
    assert {path.name for path in manager.doc_dir.glob("v[0-9]*")} == {f"v{i}" for i in range(12)}
    assert not list(manager.doc_dir.glob(".retired-*"))


def test_physical_delete_failure_keeps_quarantine_not_activatable(versions, monkeypatch):
    manager, cleanup = versions
    def denied(path):
        raise PermissionError("physical reclamation denied")
    monkeypatch.setattr(lifecycle.shutil, "rmtree", denied)
    assert cleanup._clean_kg_versions() == 2
    quarantined = list(manager.doc_dir.glob(".retired-*"))
    assert len(quarantined) == 2
    assert all((path / "nodes.json").read_text() == "[]" for path in quarantined)
    assert not manager.activate_version(1)
    assert manager.active_version() == 0
    assert cleanup._find_expired_versions() == []


def test_preview_is_revalidated_after_activation(versions):
    manager, cleanup = versions
    assert "doc_1/v1" in cleanup._find_expired_versions()
    assert manager.activate_version(1)
    assert cleanup._clean_kg_versions() == 2
    assert (manager.doc_dir / "v1/nodes.json").exists()
    assert manager.active_version() == 1


def test_orphan_directory_not_overwritten_after_failed_create(versions, monkeypatch):
    manager, _ = versions
    import kg_store
    replace = kg_store.os.replace
    def denied(source, destination):
        raise PermissionError("manifest commit denied")
    monkeypatch.setattr(kg_store.os, "replace", denied)
    with pytest.raises(PermissionError):
        manager.create_version([{"node_id": "orphan"}], [])
    assert manager.active_version() == 0
    monkeypatch.setattr(kg_store.os, "replace", replace)
    assert manager.create_version([], []) == 13
    assert json.loads((manager.doc_dir / "v12/nodes.json").read_text()) == [{"node_id": "orphan"}]


def test_parallel_writers_and_cleanup_keep_manifest_consistent(versions):
    manager, cleanup = versions
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(3)
    def create():
        barrier.wait(timeout=5)
        return KgVersionManager("1", manager.base_dir).create_version([], [])
    def clean():
        barrier.wait(timeout=5)
        return cleanup._clean_kg_versions()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(create), pool.submit(create), pool.submit(clean)]
        results = [f.result(timeout=10) for f in futures]
    assert set(results[:2]) == {12, 13}
    cleanup._clean_kg_versions()
    disk = {int(p.name[1:]) for p in manager.doc_dir.glob("v[0-9]*")}
    assert len(disk) == 10
    assert disk == {v["version"] for v in manager.list_versions()}
    assert manager.active_version() in disk


@pytest.mark.parametrize("operation", ["create", "activate", "cleanup"])
def test_operations_wait_for_real_process_lock(versions, operation):
    manager, cleanup = versions
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    script = "from filelock import FileLock; import sys; lock=FileLock(sys.argv[1]); lock.acquire(); print('locked', flush=True); sys.stdin.readline(); lock.release()"
    child = subprocess.Popen([sys.executable, "-B", "-c", script,
                              str(manager.doc_dir / ".versions.lock")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    started = Event()
    def run():
        started.set()
        if operation == "create":
            return manager.create_version([], [])
        if operation == "activate":
            return manager.activate_version(1)
        return cleanup._clean_kg_versions()
    try:
        assert child.stdout.readline().strip() == "locked"
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run)
            assert started.wait(5)
            # 父进程操作已开始，子进程持有真实文件锁期间 manifest 必须保持原状。
            from concurrent.futures import TimeoutError
            with pytest.raises(TimeoutError):
                future.result(timeout=.2)
            assert manager.active_version() == 0
            child.stdin.write("release\n")
            child.stdin.flush()
            assert future.result(timeout=10) == {"create": 12, "activate": True, "cleanup": 2}[operation]
        assert child.wait(timeout=5) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_directory_links_cannot_escape_root(versions, tmp_path):
    manager, cleanup = versions
    import os
    import subprocess
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep")
    for i in range(15):
        (outside / f"v{i}").mkdir()
    (outside / "versions.json").write_text(json.dumps({"active_version": 14,
        "versions": [{"version": i} for i in range(15)]}))
    def link(path, target):
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)],
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        else:
            path.symlink_to(target, target_is_directory=True)
    link(manager.base_dir / "doc_escape", outside)
    link(manager.doc_dir / "v100", outside)
    assert cleanup._find_expired_versions() == ["doc_1/v1", "doc_1/v2"]
    assert cleanup._clean_kg_versions() == 2
    assert sentinel.read_text() == "keep"
    assert all((outside / f"v{i}").is_dir() for i in range(15))
    metadata = json.loads(manager.versions_file.read_text())
    metadata["versions"].append({"version": 100})
    manager.versions_file.write_text(json.dumps(metadata))
    assert not manager.activate_version(100)
    assert manager.active_version() == 0
