"""一次性清理 output/logs 中已落盘的密钥形态。

默认 dry-run；加 --apply 才实际改写。
原子替换（写临时文件 + Path.replace）以防中断损坏日志。
可重复执行（幂等）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
LOG_DIR = BACKEND / "output" / "logs"

# (pattern, replacement) 显式配对 —— 比在 subn 里判断 match.groups 可读，
# 也避免"某天改了捕获组数量导致替换静默变形"。
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 已知泄露形态：file_access_token 键后跟 16-64 位 hex
    (re.compile(r'("file_access_token"\s*:\s*)"[0-9a-fA-F]{16,64}"'), r'\1"[REDACTED]"'),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"), "[REDACTED]"),
    (re.compile(r"\bLTAI[A-Za-z0-9]{12,}\b"), "[REDACTED]"),
)


def scrub_text(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in _PATTERNS:
        text, n = pattern.subn(replacement, text)
        count += n
    return text, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入（默认仅预览）")
    args = ap.parse_args()

    if not LOG_DIR.exists():
        print(f"日志目录不存在，无需清理：{LOG_DIR}")
        return 0

    total = 0
    for path in sorted(LOG_DIR.rglob("*.log*")):
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        scrubbed, n = scrub_text(original)
        if n == 0:
            continue
        total += n
        print(f"{'改写' if args.apply else '将改写'} {path.name}: {n} 处")
        if args.apply:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(scrubbed, encoding="utf-8")
            tmp.replace(path)
    print(f"{'已' if args.apply else '将'}清理 {total} 处")
    if not args.apply and total:
        print("加 --apply 执行实际清理。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
