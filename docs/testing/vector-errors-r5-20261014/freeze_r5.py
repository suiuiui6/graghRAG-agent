from pathlib import Path
import json,hashlib,shutil,datetime
r=Path('.tmp/vector-errors-r5-20261014');out=Path('docs/testing/vector-errors-r5-20261014');out.mkdir(parents=True,exist_ok=True)
# Explicit receipts bind the final snapshot. Historical scripts are evidence only, never executed.
inputs=[Path(p) for p in ['docs/contracts/2026-10-14-vector-error-semantics.md','docs/plans/2026-10-14-vector-error-fix.md','docs/review/2026-10-14-vector-error-consumer-audit.md','docs/review/2026-10-14-vector-errors-design-review.md','.tmp/vector-errors-testenv-20261014/pyproject.toml','.tmp/vector-errors-testenv-20261014/uv.lock','.tmp/vector-errors-testenv-20261014/runtime-pins.json']]
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'commands':[{'command':'.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-errors-r5-20261014/red_contract.py','exit':1,'kind':'red before implementation'},{'command':'.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-errors-r5-20261014/execute_r4b.py green','exit':0,'kind':'old full specialized regressions'},{'command':'.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-errors-r5-20261014/chroma_errors.py','exit':0,'kind':'real Chroma 15 native observations'},{'command':'.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/vector-errors-r5-20261014/test_errors.py','exit':0,'kind':'5 unittest groups; real Lance+consumer AST+real logging processors'}],'additional_commands':[{'command':'.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/vector-errors-r5-20261014/test_facade.py','red_exit':1,'final_exit':0,'kind':'real facade same/orthogonal/opposite score and prefilter plus huge integer vector validation'}],'offline_env':{'PYTHON_DOTENV_DISABLED':'1','HF_HUB_OFFLINE':'1'},'review':'PENDING; candidate snapshot, not approval'}
(r/'r5-execution-receipt.json').write_text(json.dumps(receipt,indent=2))
for p in inputs:
 dest=out/'inputs'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for p in r.rglob('*'):
 if p.is_file() and (p.parent==r or 'baseline-r4b' in p.parts or p.parent.name=='final') and (p.suffix in ('.py','.json','.log','.exit','.md') or p.name in ('LICENSE-MIT','LICENSE-APACHE')):
  dest=out/p.relative_to(r);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='r5-freeze-manifest.json'}
(out/'r5-freeze-manifest.json').write_text(json.dumps({'utc':receipt['utc'],'files':files,'review':'PENDING'},indent=2))
print('frozen',len(files))
