from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
OUT_PATH = EVAL_DIR / "backend_validation_summary.json"
DEFAULT_COMMAND = ".\\.venv\\Scripts\\python -m pytest tests -q"

_SUMMARY_RE = re.compile(r"^\d+\s+\w+(?:,\s+\d+\s+\w+)*\s+in\s+.+$", re.MULTILINE)
_WARNING_TEST_RE = re.compile(r"^(tests/[^\r\n:]+::[^\r\n]+)$", re.MULTILINE)
_WARNING_DETAIL_RE = re.compile(r"UserWarning:\s*([^\r\n]+)")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_warning_detail(detail: str) -> str:
    normalized = (detail or "").strip()
    if "pkg_resources is deprecated as an API" in normalized:
        return "jieba pkg_resources deprecation warning"
    return normalized


def _pytest_subprocess_env() -> dict[str, str]:
    temp_root = REPO_ROOT / ".pytest-tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    temp_root_str = str(temp_root)
    env["TMP"] = temp_root_str
    env["TEMP"] = temp_root_str
    env["TMPDIR"] = temp_root_str
    return env


def _backend_python_executable() -> Path:
    python_exe = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        raise FileNotFoundError(f"Backend venv python not found: {python_exe}")
    return python_exe


def _run_pytest_in_process(pytest_args: list[str], *, cwd: Path) -> tuple[int, str]:
    env = _pytest_subprocess_env()
    command = [str(_backend_python_executable()), "-m", "pytest", *pytest_args]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    combined_output = "\n".join(
        part for part in [result.stdout, result.stderr] if part
    )
    return int(result.returncode), combined_output


def parse_pytest_output(pytest_output: str) -> dict[str, Any]:
    output = pytest_output or ""
    summary_match = None
    for match in _SUMMARY_RE.finditer(output):
        summary_match = match

    summary = summary_match.group(0).strip() if summary_match else "n/a"

    warnings: list[str] = []
    if "warnings summary" in output.lower():
        test_match = _WARNING_TEST_RE.search(output)
        detail_match = _WARNING_DETAIL_RE.search(output)
        if test_match and detail_match:
            warnings.append(
                f"{test_match.group(1)} -> {_normalize_warning_detail(detail_match.group(1))}"
            )

    return {
        "summary": summary,
        "warnings": warnings,
    }


def build_backend_validation_summary(
    *,
    command: str,
    working_directory: str,
    exit_code: int,
    pytest_output: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    parsed = parse_pytest_output(pytest_output)
    return {
        "generated_at": generated_at or _utc_now(),
        "command": command,
        "working_directory": working_directory,
        "exit_code": int(exit_code),
        "summary": parsed["summary"],
        "warnings": parsed["warnings"],
    }


def run_backend_validation() -> dict[str, Any]:
    exit_code, combined_output = _run_pytest_in_process(["tests", "-q"], cwd=BACKEND_DIR)
    summary = build_backend_validation_summary(
        command=DEFAULT_COMMAND,
        working_directory=str(BACKEND_DIR),
        exit_code=exit_code,
        pytest_output=combined_output,
    )
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    summary = run_backend_validation()
    print(f"Wrote {OUT_PATH}")
    print(summary["summary"])
    if summary["exit_code"] != 0:
        raise SystemExit(summary["exit_code"])


if __name__ == "__main__":
    main()
