"""Archive tested sources and explicit receipts, not native DB artifacts."""
import hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
r=Path(__file__).resolve().parent;repo=r.parents[1];dest=repo/'docs/testing/vector-r6-20261014'
assert not dest.exists(),'freeze destination must be new'
receipt=json.loads((r/'resume-r6-regressions.json').read_text())
assert receipt['unchanged'] and all(x['exit_code']==0 for x in receipt['commands'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in receipt['inputs_after'].items():assert sha(repo/name)==digest,name
dest.mkdir(parents=True)
files=list(r.glob('*.py'))+list(r.glob('*.json'))+list(r.glob('*.log'))+list(r.glob('*.exit'))+list((r/'current-consumer').glob('*.py'))
for src in files:
 target=dest/src.relative_to(r);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
debug=[]
for src in (repo/'.tmp/vector-r6-debug-20261014').iterdir():
 if src.is_file() and src.suffix in ('.py','.json','.log','.exit'):
  target=dest/'debug-evidence'/src.name;target.parent.mkdir(exist_ok=True);shutil.copy2(src,target);debug.append({'source':str(src.relative_to(repo)),'sha256':sha(src),'archived':str(target.relative_to(dest))})
envfiles=[repo/'.tmp/vector-errors-testenv-20261014/uv.lock',repo/'.tmp/vector-errors-testenv-20261014/environment-receipt.json',repo/'.tmp/vector-errors-testenv-20261014/runtime-pins.json']
for src in envfiles:
 target=dest/'locked-environment'/src.name;target.parent.mkdir(exist_ok=True);shutil.copy2(src,target)
consumers={name:{'current_source_sha256':sha(repo/'backend'/name),'executed_copy_sha256':sha(r/'current-consumer'/name)} for name in ('retrieval.py','logging_config.py','source_control.py','evidence_trace.py')}
manifest={'utc':datetime.now(timezone.utc).isoformat(),'scope':'isolated static-generation MVP and current consumer AST subset; no production integration, no migration','validated_receipt':'resume-r6-regressions.json','historical_receipts':'All other prior manifests/logs retained as history; not evidence of this final run','validated_inputs':receipt['inputs_after'],'consumers':consumers,'debug_evidence':debug,'files':{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}}
(dest/'r6-freeze-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'files':len(manifest['files']),'receipt_commands':len(receipt['commands']),'debug_files':len(debug),'manifest_sha256':sha(dest/'r6-freeze-manifest.json'),'consumer_copies_match':all(v['current_source_sha256']==v['executed_copy_sha256'] for v in consumers.values())}))
