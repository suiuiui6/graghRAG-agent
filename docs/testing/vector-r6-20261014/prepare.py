import hashlib,json,shutil
from pathlib import Path
r=Path(__file__).resolve().parent; repo=r.parents[1]; old=repo/'docs/testing/vector-errors-r5-20261014'
m=json.loads((old/'r5-freeze-manifest.json').read_text())['files']
assert len(m)==284
for name,sha in m.items():
 p=old/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
 q=r/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
(r/'baseline-r5-receipt.json').write_text(json.dumps({'files':len(m),'drift':0,'manifest_sha256':hashlib.sha256((old/'r5-freeze-manifest.json').read_bytes()).hexdigest()},indent=2))
sources=r/'current-consumer';sources.mkdir(exist_ok=True)
for name in ('retrieval.py','source_control.py','evidence_trace.py','logging_config.py'):shutil.copy2(repo/'backend'/name,sources/name)
(r/'current-consumer-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.glob('*.py')},indent=2))
