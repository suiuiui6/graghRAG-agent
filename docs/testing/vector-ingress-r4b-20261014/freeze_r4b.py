"""Freeze r4b only. Check final tested source hashes and prior r4 immutability."""
import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
repo=root.parents[1]
dest=repo/'docs/testing/vector-ingress-r4b-20261014'
old=repo/'docs/testing/vector-ingress-r4-20261014'
old_manifest=json.loads((old/'freeze-manifest.json').read_text())
for name,digest in old_manifest['files'].items(): assert hashlib.sha256((old/name).read_bytes()).hexdigest()==digest,name
run=json.loads((root/'green-execution-manifest.json').read_text())
for name,digest in run['inputs'].items(): assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
assert all(c['exit_code']==0 for c in run['commands'])
assert len(json.loads((root/'red-wide-matrix-lance.json').read_text())['differences'])==72
for name in ['green-wide-matrix-lance.json','green-raw-matrix.json','fresh-lance.json']:
    assert not json.loads((root/name).read_text())['differences'],name
dest.mkdir(exist_ok=True)
assert not (dest/'freeze-manifest.json').exists(),'freeze is immutable; choose a new revision'
# Copied historical archive/finalize helpers are excluded: they point at old revisions.
for p in root.iterdir():
    if p.is_file() and p.name not in ('archive.py','finalize.py'):
        shutil.copy2(p,dest/p.name)
out=dest/'final';out.mkdir(exist_ok=True)
for p in (root/'final').iterdir():
    if p.is_file(): shutil.copy2(p,out/p.name)
files={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file()}
(dest/'freeze-manifest.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'files':files,'old_r4_files_verified':len(old_manifest['files']),'final_tested_inputs_verified':True,'excluded_historical_helpers':['archive.py','finalize.py']},indent=2))
print(json.dumps({'files':len(files),'old_r4_files_verified':len(old_manifest['files']),'final_tested_inputs_verified':True}))
