from pathlib import Path

from tests import conftest


TESTS_DIR = Path(__file__).resolve().parent


def test_should_ignore_top_level_test_artifact_directories(monkeypatch):
    original_is_dir = Path.is_dir
    artifact_names = {
        "tmp_basetemp_deadbeef",
        "tmp_probe_tempfile",
        "_sandbox_tmp",
        "_tmp_worker_support_artifacts_1234",
    }

    def fake_is_dir(path):
        return path.name in artifact_names or original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)

    assert conftest._should_ignore_test_artifact_path(TESTS_DIR / "tmp_basetemp_deadbeef")
    assert conftest._should_ignore_test_artifact_path(TESTS_DIR / "tmp_probe_tempfile")
    assert conftest._should_ignore_test_artifact_path(TESTS_DIR / "_sandbox_tmp")
    assert conftest._should_ignore_test_artifact_path(TESTS_DIR / "_tmp_worker_support_artifacts_1234")


def test_keeps_real_tests_and_nested_paths_collectable():
    assert not conftest._should_ignore_test_artifact_path(TESTS_DIR / "test_runtime_recovery.py")
    assert not conftest._should_ignore_test_artifact_path(TESTS_DIR / "fixtures")
    assert not conftest._should_ignore_test_artifact_path(TESTS_DIR / "tmp_basetemp_deadbeef.txt")
    assert not conftest._should_ignore_test_artifact_path(TESTS_DIR / "nested" / "tmp_basetemp_deadbeef")


def test_pytest_ignore_collect_only_skips_matching_top_level_directories(monkeypatch):
    original_is_dir = Path.is_dir

    def fake_is_dir(path):
        return path.name == "_tmp_debug_deadbeef" or original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)

    assert conftest.pytest_ignore_collect(TESTS_DIR / "_tmp_debug_deadbeef", None) is True
    assert conftest.pytest_ignore_collect(TESTS_DIR / "test_runtime_recovery.py", None) is False