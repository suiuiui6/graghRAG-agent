"""Capture command identity, exit, output and immutable source hashes."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parents[1] / "docs/testing/sqlite-numpy-r7-20261015"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.suffix in (".py", ".toml", ".lock")}


if __name__ == "__main__":
    label, *command = sys.argv[1:]
    before = hashes()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    p = subprocess.run(command, cwd=ROOT, capture_output=True)
    after = hashes()
    (EVIDENCE / (label+".stdout.log")).write_bytes(p.stdout)
    (EVIDENCE / (label+".stderr.log")).write_bytes(p.stderr)
    receipt = {"command":command,"cwd":str(ROOT),"started_utc":started,"finished_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"exit_code":p.returncode,"source_before":before,"source_after":after,"source_drift":before != after}
    (EVIDENCE / (label+".json")).write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    sys.stdout.buffer.write(p.stdout)
    sys.stderr.buffer.write(p.stderr)
    print(json.dumps({"label":label,"exit_code":p.returncode,"source_drift":before != after}))
    sys.exit(p.returncode)
