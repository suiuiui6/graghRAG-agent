"""Tiny filesystem fixtures only; these are not model or real-asset experiments."""

import importlib.util
import hashlib
import json
import os
from pathlib import Path

import pytest


MODULE = Path(__file__).parents[1] / "research" / "isolation_snapshot.py"


def api():
    assert MODULE.exists(), "physical snapshot preparation API must exist"
    spec = importlib.util.spec_from_file_location("isolation_snapshot_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(path, value=b"tiny fixture"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return path


def fixture_tree(tmp_path):
    root = tmp_path / "project"
    put(root / "backend" / "main.py", b"# never imported\n")
    put(root / "backend" / "routes" / "sample.py")
    put(root / "backend" / "uv.lock")
    put(root / "backend" / "pyproject.toml")
    put(root / "backend" / "config" / "domain_dict.yaml", b"terms: []")
    put(root / "backend" / "output" / "runtime" / "runtime.db")
    put(root / "backend" / "output" / "uploads" / "private.txt")
    put(root / "backend" / ".env", b"do not copy")
    put(root / "backend" / ".venv" / "Lib" / "site-packages" / "tiny" / "__init__.py")
    base = tmp_path / "base-python"
    executable = put(base / "python.exe", b"fake executable: never executed")
    put(base / "python312.dll")
    put(base / "DLLs" / "tiny.pyd")
    put(base / "Lib" / "pathlib.py")
    put(base / "Lib" / "site-packages" / "global.py")
    return root, executable


def test_safe_files_skips_secrets_logs_and_bytecode(tmp_path):
    put(tmp_path / "ok.py")
    for name in (".env", ".env.local", "server.log", "logs/x.txt", "__pycache__/a.pyc", "x.pyo"):
        put(tmp_path / name)
    assert api().safe_files(tmp_path, [tmp_path]) == [tmp_path / "ok.py"]


def test_safe_files_rejects_escape_and_file_hardlink(tmp_path):
    module = api()
    outside = put(tmp_path.parent / (tmp_path.name + "-outside"))
    with pytest.raises(ValueError):
        module.safe_files(tmp_path, [outside])
    original = put(tmp_path / "original.py")
    os.link(original, tmp_path / "alias.py")
    with pytest.raises(ValueError):
        module.safe_files(tmp_path, [original])


def test_safe_files_rejects_link_ancestor(tmp_path):
    module = api()
    actual = tmp_path / "actual"
    put(actual / "a.py")
    link = tmp_path / "link"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("host does not allow unprivileged symbolic links")
    with pytest.raises(ValueError):
        module.safe_files(link, [link / "a.py"])


def test_copy_verified_is_independent_and_refuses_overwrite(tmp_path):
    module = api()
    source = put(tmp_path / "source", b"independent")
    target = tmp_path / "new" / "target"
    record = module.copy_verified(source, target)
    assert target.read_bytes() == source.read_bytes()
    assert not os.path.samestat(source.stat(), target.stat())
    assert record["before"]["sha256"] == record["after"]["sha256"] == record["destination"]["sha256"]
    with pytest.raises(ValueError):
        module.copy_verified(source, target)


def test_prepare_snapshot_whitelist_runtime_and_manifest(tmp_path):
    module = api()
    root, executable = fixture_tree(tmp_path)
    manifest = module.prepare_snapshot(root, "tiny-1", executable)
    run = root / "backend" / "output" / "research-isolation" / "tiny-1"
    assert manifest["status"] == "verified"
    assert (run / "backend" / "main.py").exists()
    assert (run / "backend" / "output" / "runtime" / "runtime.db").exists()
    assert (run / "python" / "Lib" / "site-packages" / "tiny" / "__init__.py").exists()
    assert not (run / "python" / "Lib" / "site-packages" / "global.py").exists()
    assert not (run / "backend" / ".env").exists()
    assert not (run / "backend" / "output" / "uploads").exists()
    assert json.loads((run / "manifest.json").read_text("utf-8"))["status"] == "verified"
    assert all(item["before"]["sha256"] == item["after"]["sha256"] for item in manifest["files"])
    with pytest.raises(ValueError):
        module.prepare_snapshot(root, "tiny-1", executable)


@pytest.mark.parametrize("run_id", ["../escape", "", "x" * 65, "a.b", "a/b"])
def test_prepare_rejects_bad_run_ids(tmp_path, run_id):
    root, executable = fixture_tree(tmp_path)
    with pytest.raises(ValueError):
        api().prepare_snapshot(root, run_id, executable)


def test_prepare_rejects_active_wal_before_creating_target(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / "output" / "runtime" / "runtime.db-wal", b"active")
    with pytest.raises(ValueError, match="WAL"):
        api().prepare_snapshot(root, "wal", executable)
    assert not (root / "backend" / "output" / "research-isolation" / "wal").exists()


@pytest.mark.parametrize("entry", ["C:\\outside\n", "../../outside\n", "/outside\n"])
def test_prepare_rejects_unsafe_pth(tmp_path, entry):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / ".venv" / "Lib" / "site-packages" / "unsafe.pth", entry.encode())
    with pytest.raises(ValueError, match="pth"):
        api().prepare_snapshot(root, "pth", executable)


def test_prepare_copies_import_pth_as_inert_data(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / ".venv" / "Lib" / "site-packages" / "inert.pth", b"import never_execute_me\n")
    manifest = api().prepare_snapshot(root, "inert", executable)
    assert manifest["pth_activation"] == "DISABLED_BY_MINUS_S"
    assert manifest["required_python_flags"] == ["-I", "-S", "-B"]


def test_prepare_rejects_venv_launcher_as_base_python(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(executable.parent / "pyvenv.cfg")
    with pytest.raises(ValueError, match="base"):
        api().prepare_snapshot(root, "launcher", executable)


def test_prepare_detects_source_drift_and_preserves_failed_target(tmp_path, monkeypatch):
    module = api()
    root, executable = fixture_tree(tmp_path)
    original = module.copy_verified
    calls = 0

    def drift(source, target):
        nonlocal calls
        result = original(source, target)
        calls += 1
        if calls == 2:
            (root / "backend" / "main.py").write_bytes(b"source changed")
        return result

    monkeypatch.setattr(module, "copy_verified", drift)
    with pytest.raises(ValueError, match="drift"):
        module.prepare_snapshot(root, "drift", executable)
    run = root / "backend" / "output" / "research-isolation" / "drift"
    assert run.exists()
    assert json.loads((run / "manifest.json").read_text("utf-8"))["status"] == "failed"


def test_prepare_copies_only_explicit_domain_config_and_all_package_resources(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / "config" / "domain_dict.yaml", b"terms: []")
    put(root / "backend" / "config" / "credentials.yaml", b"private")
    put(root / "backend" / ".venv" / "Lib" / "site-packages" / "tiny.dist-info" / "METADATA")
    put(root / "backend" / ".venv" / "Lib" / "site-packages" / "tiny" / "tokenizer.json")
    manifest = api().prepare_snapshot(root, "config", executable)
    run = Path(manifest["run_root"])
    assert (run / "backend" / "config" / "domain_dict.yaml").is_file()
    assert not (run / "backend" / "config" / "credentials.yaml").exists()
    assert (run / "python" / "Lib" / "site-packages" / "tiny.dist-info" / "METADATA").is_file()
    assert (run / "python" / "Lib" / "site-packages" / "tiny" / "tokenizer.json").is_file()


@pytest.mark.parametrize("name", [".env", ".env.local", "private.log", "__pycache__/a.pyc"])
def test_copy_verified_refuses_excluded_direct_sources(tmp_path, name):
    source = put(tmp_path / name)
    with pytest.raises(ValueError, match="excluded"):
        api().copy_verified(source, tmp_path / "target")


def test_prepare_requires_python312_runtime_dll(tmp_path):
    root, executable = fixture_tree(tmp_path)
    (executable.parent / "python312.dll").unlink()
    with pytest.raises(ValueError, match="python312.dll"):
        api().prepare_snapshot(root, "missing-runtime", executable)


def test_manifest_has_frozen_destination_inventory_digest(tmp_path):
    root, executable = fixture_tree(tmp_path)
    manifest = api().prepare_snapshot(root, "inventory", executable)
    assert manifest["destination_file_count"] == len(manifest["files"])
    inventory = {str(Path(item["target"]).relative_to(Path(manifest["run_root"]))): item["destination"]["sha256"]
                 for item in manifest["files"]}
    expected = hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert manifest["destination_inventory_sha256"] == expected


@pytest.mark.parametrize("missing_kind", ["missing", "directory"])
def test_prepare_requires_regular_domain_dictionary_before_target_creation(tmp_path, missing_kind):
    root, executable = fixture_tree(tmp_path)
    domain = root / "backend" / "config" / "domain_dict.yaml"
    domain.unlink()
    if missing_kind == "directory":
        domain.mkdir()
    with pytest.raises(ValueError, match="domain_dict.yaml"):
        api().prepare_snapshot(root, "domain-required", executable)
    assert not (root / "backend" / "output" / "research-isolation" / "domain-required").exists()


def test_prepare_root_whitelist_uses_only_exact_project_configs(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / "private.toml")
    put(root / "backend" / "historical.lock")
    manifest = api().prepare_snapshot(root, "root-whitelist", executable)
    backend = Path(manifest["run_root"]) / "backend"
    assert (backend / "uv.lock").is_file()
    assert (backend / "pyproject.toml").is_file()
    assert not (backend / "private.toml").exists()
    assert not (backend / "historical.lock").exists()


@pytest.mark.parametrize("scratch", [".pytest-temp", ".pytest-tmp", ".pytest_cache", "research-isolation-tests"])
def test_prepare_excludes_research_test_scratch_before_traversal(tmp_path, scratch):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / "research" / scratch / "private.py")
    manifest = api().prepare_snapshot(root, "scratch", executable)
    copied = Path(manifest["run_root"]) / "backend" / "research" / scratch
    assert not copied.exists()


def test_prepare_rejects_active_rollback_journal_before_target_creation(tmp_path):
    root, executable = fixture_tree(tmp_path)
    put(root / "backend" / "output" / "runtime" / "runtime.db-journal", b"rollback active")
    with pytest.raises(ValueError, match="journal"):
        api().prepare_snapshot(root, "journal", executable)
    assert not (root / "backend" / "output" / "research-isolation" / "journal").exists()
