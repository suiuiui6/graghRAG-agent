"""Archive the completed runs; no database or product mutation."""
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
repo = root.parents[1]
dest = repo/'docs/testing/vector-numeric-r3-20261014'
dest.mkdir(exist_ok=True)
for phase in ['red', 'green']:
    shutil.copytree(root/phase, dest/phase, dirs_exist_ok=True)
for p in root.iterdir():
    if p.is_file() and p.suffix in ['.py', '.json']: shutil.copy2(p, dest/p.name)
manifest = {'utc': datetime.now(timezone.utc).isoformat(), 'files': {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='freeze-manifest.json'}}
for phase in ['red','green']:
    run=json.loads((dest/phase/'manifest.json').read_text())
    assert run['inputs_before']==run['inputs_after']
    for source, digest in run['inputs_before'].items():
        p=repo/source
        if phase=='green': assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,source
manifest['red_green_input_hash_verified'] = True
(dest/'freeze-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'files':len(manifest['files']),'green_snapshot_verified':True}))
