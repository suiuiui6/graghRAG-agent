"""错误策略源码遍历的范围与剪枝回归。"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "error_policy_walk_subject", Path(__file__).with_name("test_error_handling_policy.py")
)
policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(policy)


def test_root_tests_directory_is_pruned_before_iteration(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    tests = backend / "tests"
    tests.mkdir(parents=True)
    (tests / "generated.py").write_text("print('测试产物')", encoding="utf-8")
    (backend / "library.py").write_text("value = 1", encoding="utf-8")
    monkeypatch.setattr(policy, "BACKEND", backend)
    original_iterdir = Path.iterdir

    def checked_iterdir(path):
        assert path != tests, "排除的根测试目录不得进入遍历"
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", checked_iterdir)
    assert {rel for _, rel in policy._sources()} == {"library.py"}


def test_unimported_research_and_nested_tests_sources_remain_in_scope(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    nested = backend / "research" / "tests"
    nested.mkdir(parents=True)
    expected = {"library.py", "research/unimported.py", "research/tests/helper.py"}
    for rel in expected:
        (backend / rel).write_text("value = 1", encoding="utf-8")
    monkeypatch.setattr(policy, "BACKEND", backend)
    assert {rel for _, rel in policy._sources()} == expected
