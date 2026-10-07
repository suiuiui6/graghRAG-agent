# 必须在任何测试模块之前加载**真** structlog。
#
# test_community_global_mode.py 与 test_kg_indexed_recall.py 在 import 期用
# `if "structlog" not in sys.modules` 往 sys.modules 塞一个 SimpleNamespace
# 假 structlog。若它们先被收集，logging_config 会绑定到这个假模块，
# get_logger() 退化成 no-op —— 于是所有依赖日志的测试在全量跑时静默失败、
# 单独跑却通过（已实测复现）。
#
# conftest 先 import 真模块，使其 `not in sys.modules` 条件不成立，stub 自动失效；
# 那两处模块级 stub 因此无需改动。
import structlog  # noqa: F401

import re
import shutil
import uuid
from pathlib import Path

import pytest


_TESTS_DIR = Path(__file__).resolve().parent
_SANDBOX_TMP_ROOT = _TESTS_DIR / "_sandbox_tmp"
_TEST_ARTIFACT_PREFIXES = (
    "tmp_basetemp_",
    "tmp_probe_",
    "_sandbox_",
    "_tmp_",
)


def _sanitize_tmp_prefix(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return cleaned or "tmp"


def _should_ignore_test_artifact_path(path: Path) -> bool:
    candidate = Path(path)
    if candidate.parent != _TESTS_DIR or not candidate.is_dir():
        return False
    name = candidate.name
    return any(name.startswith(prefix) for prefix in _TEST_ARTIFACT_PREFIXES)


def pytest_ignore_collect(collection_path, config):
    return _should_ignore_test_artifact_path(Path(str(collection_path)))


@pytest.fixture
def sandbox_tmp_path(request):
    """Create a repo-local temp directory compatible with the managed sandbox."""
    prefix = _sanitize_tmp_prefix(request.node.name)
    root = _SANDBOX_TMP_ROOT / prefix
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)