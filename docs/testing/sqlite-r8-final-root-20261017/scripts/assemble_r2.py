from pathlib import Path
import json,hashlib,shutil,subprocess,os,sys
r=Path('D:/graghRAG-agent');old=r/'.tmp/sqlite-r8-combined-20261017';out=r/'.tmp/sqlite-r8-combined-r2-20261017';out.mkdir(exist_ok=False)
shutil.copytree(old/'backend',out/'backend',ignore=shutil.ignore_patterns('test-output','output','__pycache__','*.sqlite*'))
s=r/'docs/testing/sqlite-vector-r8-r2-20261017';m=json.loads((s/'manifest.json').read_text())
for n,v in m.items():assert hashlib.sha256((s/n).read_bytes()).hexdigest()==v['sha256'],n
shutil.copytree(s/'backend',out/'backend',dirs_exist_ok=True);shutil.copytree(s/'tests',out/'adapter-tests');shutil.copy2(old/'test_real_integration.py',out/'test_real_integration.py')
before={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*.py')}
cmd=[str(r/'.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe'),'-B','-X','utf8','-m','pytest',str(out/'backend/tests'),str(out/'adapter-tests'),str(out/'test_real_integration.py'),'-q','-p','no:cacheprovider']
env=dict(os.environ,PYTHONPATH=str(out/'backend'),PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',GRAPHRAG_RUNTIME_ARTIFACTS_DIR=str(out/'artifacts'))
p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,encoding='utf8');(out/'tests.log').write_text(p.stdout+p.stderr,encoding='utf8')
after={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*.py')}
receipt={'command':cmd,'exit_code':p.returncode,'cwd':str(out),'adapter_files_verified':len(m),'manifest_sha256':hashlib.sha256((s/'manifest.json').read_bytes()).hexdigest(),'source_before':before,'source_after':after,'source_drift':before!=after}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(p.stdout[-1200:]);assert before==after;sys.exit(p.returncode)
