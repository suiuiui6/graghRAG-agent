"""Research admission check, distinct from software correctness tests.

Never updates the historical freeze and returns nonzero on drift.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
freeze = ROOT / 'docs/superpowers/plans/scope-pilot/gold-review-v2/local-freeze-v2-20261008.json'
expected = json.loads(freeze.read_text(encoding='utf-8'))['production_files_sha256']
if not expected:
    raise SystemExit('empty research freeze cannot establish admission')
records = {}
for path, digest in expected.items():
    file = ROOT / path
    actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
    records[path] = {'expected': digest, 'actual': actual, 'match': actual == digest}
matched = all(item['match'] for item in records.values())
print(json.dumps({'status': 'PASS' if matched else 'DRIFT_REQUIRES_REVIEW',
                  'research_execution_authorized': False, 'files': records}, ensure_ascii=False, indent=2))
raise SystemExit(0 if matched else 1)
