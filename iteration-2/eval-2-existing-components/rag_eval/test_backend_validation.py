from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend_validation import (
    _pytest_subprocess_env,
    REPO_ROOT,
    BACKEND_DIR,
    build_backend_validation_summary,
    parse_pytest_output,
    _run_pytest_in_process,
)


def test_parse_pytest_output_extracts_latest_summary_and_warning() -> None:
    output = """
........................................................................ [100%]
============================== warnings summary ===============================
tests/test_hybrid_retrieval_trimming.py::test_bm25_query_uses_same_tokenizer_as_index
  D:\\graghRAG-agent\\backend\\.venv\\Lib\\site-packages\\jieba\\_compat.py:18: UserWarning: pkg_resources is deprecated as an API.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
232 passed, 1 warning in 12.41s
""".strip()

    parsed = parse_pytest_output(output)

    assert parsed["summary"] == "232 passed, 1 warning in 12.41s"
    assert parsed["warnings"] == [
        "tests/test_hybrid_retrieval_trimming.py::test_bm25_query_uses_same_tokenizer_as_index -> jieba pkg_resources deprecation warning"
    ]


def test_build_backend_validation_summary_includes_command_and_exit_code() -> None:
    payload = build_backend_validation_summary(
        command=".\\\\venv\\\\Scripts\\\\python -m pytest tests -q",
        working_directory="D:\\graghRAG-agent\\backend",
        exit_code=0,
        pytest_output="""
232 passed, 1 warning in 12.41s
""".strip(),
        generated_at="2026-06-14T21:05:00+08:00",
    )

    assert payload["generated_at"] == "2026-06-14T21:05:00+08:00"
    assert payload["command"] == ".\\\\venv\\\\Scripts\\\\python -m pytest tests -q"
    assert payload["working_directory"] == "D:\\graghRAG-agent\\backend"
    assert payload["exit_code"] == 0
    assert payload["summary"] == "232 passed, 1 warning in 12.41s"
    assert payload["warnings"] == []


def test_parse_pytest_output_extracts_failure_summary() -> None:
    output = """
=========================== short test summary info ===========================
FAILED tests/test_runtime_caching.py::test_get_or_create_returns_new_session_when_existing_conversation_expired
1 failed, 256 passed, 1 warning in 14.13s
""".strip()

    parsed = parse_pytest_output(output)

    assert parsed["summary"] == "1 failed, 256 passed, 1 warning in 14.13s"


def test_pytest_subprocess_env_overrides_temp_into_workspace() -> None:
    env = _pytest_subprocess_env()

    expected = str(REPO_ROOT / ".pytest-tmp")
    assert env["TMP"] == expected
    assert env["TEMP"] == expected
    assert env["TMPDIR"] == expected
    assert os.path.isdir(expected)


def test_run_pytest_runner_uses_backend_venv_subprocess(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="232 passed in 12.41s\n", stderr="")

    monkeypatch.setattr(
        sys.modules["backend_validation"],
        "subprocess",
        SimpleNamespace(run=fake_run),
        raising=False,
    )

    exit_code, combined_output = _run_pytest_in_process(["tests", "-q"], cwd=BACKEND_DIR)

    backend_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    assert exit_code == 0
    assert combined_output.strip() == "232 passed in 12.41s"
    assert calls["command"] == [str(backend_python), "-m", "pytest", "tests", "-q"]
    assert calls["kwargs"]["cwd"] == BACKEND_DIR
    assert calls["kwargs"]["capture_output"] is True
    assert calls["kwargs"]["text"] is True
    assert calls["kwargs"]["env"]["TMP"] == str(REPO_ROOT / ".pytest-tmp")
