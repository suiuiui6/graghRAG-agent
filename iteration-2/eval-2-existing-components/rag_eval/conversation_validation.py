from __future__ import annotations

import json
from pathlib import Path

from backend_validation import build_backend_validation_summary, _run_pytest_in_process

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
OUT_PATH = EVAL_DIR / "conversation_validation_summary.json"
DEFAULT_COMMAND = ".\\.venv\\Scripts\\python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no"


def run_conversation_validation() -> dict:
    exit_code, combined_output = _run_pytest_in_process(
        ["tests/test_conversation_rewrite.py", "-q", "-s", "--capture=no"],
        cwd=BACKEND_DIR,
    )
    summary = build_backend_validation_summary(
        command=DEFAULT_COMMAND,
        working_directory=str(BACKEND_DIR),
        exit_code=exit_code,
        pytest_output=combined_output,
    )
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    summary = run_conversation_validation()
    print(f"Wrote {OUT_PATH}")
    print(summary["summary"])
    if summary["exit_code"] != 0:
        raise SystemExit(summary["exit_code"])


if __name__ == "__main__":
    main()
