from pathlib import Path
import json,hashlib,shutil
r=Path('.tmp/vector-errors-r5-20261014'); src=Path('docs/testing/vector-ingress-r4b-20261014')
m=json.loads((src/'freeze-manifest.json').read_text())
for name,digest in m['files'].items():
 p=src/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
 out=r/'baseline-r4b'/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
(r/'baseline-receipt.json').write_text(json.dumps({'source':'docs/testing/vector-ingress-r4b-20261014','freeze_sha256':hashlib.sha256((src/'freeze-manifest.json').read_bytes()).hexdigest(),'files_verified':len(m['files']),'immutable':True},indent=2))
