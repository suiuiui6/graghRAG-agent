"""Repair the proven test overwrite; refuse any unexpected current bytes.

This is a one-time corrective tool, not an index rebuild or freeze update.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
relative = 'backend/output/runtime/table_artifact.json'
target = root / relative
historical = root / 'backend/output/research-isolation/capture-prep-20261011' / relative
record = json.loads((root / 'docs/superpowers/plans/scope-pilot/gold-review-v2/local-preflight-20261008.json')
                    .read_text(encoding='utf-8'))['metadata_audit']['json_artifacts'][relative]
expected = record['sha256']
known_overwrite = 'bc4e79720219f061278c91f7e2782d951eede5e508fc5f833fffa946341c6327'
raw = historical.read_bytes()
current = target.read_bytes()
hash_bytes = lambda data: hashlib.sha256(data).hexdigest()
if hash_bytes(raw) != expected or len(json.loads(raw)['rows']) != 2:
    raise SystemExit('historical recovery copy does not match the recorded original')
if hash_bytes(current) != known_overwrite or json.loads(current) != {'rows': []}:
    raise SystemExit('current bytes are not the proven empty snapshot overwrite; no mutation')
evidence = root / '.tmp/test-artifact-overwrite-evidence'
evidence.mkdir(parents=True, exist_ok=True)
(evidence / 'table_artifact.empty.json').write_bytes(current)
replacement = target.with_name('.table-artifact-recovery.tmp')
replacement.write_bytes(raw)
if hash_bytes(target.read_bytes()) != known_overwrite:
    replacement.unlink()
    raise SystemExit('current artifact changed during repair; no replacement')
os.replace(replacement, target)
receipt = {'time_utc': datetime.now(timezone.utc).isoformat(), 'path': relative,
           'before_sha256': known_overwrite, 'after_sha256': hash_bytes(target.read_bytes()),
           'original_evidence': '2026-10-08 preflight metadata plus immutable 2026-10-11 capture copy',
           'recovered_rows': 2, 'historical_copy_unchanged': hash_bytes(historical.read_bytes()) == expected,
           'research_freeze_updated': False}
(root / 'docs/testing/2026-10-13-artifact-recovery-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt))
