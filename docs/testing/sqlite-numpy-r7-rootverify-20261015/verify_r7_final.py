import datetime,hashlib,importlib.metadata,json,os,shutil,subprocess,tomllib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
src=root/'docs/testing/sqlite-numpy-r7-final-20261015'
mf=src/'manifest.json';mh=hashlib.sha256(mf.read_bytes()).hexdigest()
assert mh=='fcf0ecf3cbf8c5a57ceb98d970333a7c54f9de09ab5ec6951d2fcbfeab41fc2d'
m=json.loads(mf.read_text(encoding='utf-8'))
for name,item in m.items():
    p=(src/name).resolve();assert p.is_relative_to(src.resolve())
    assert p.stat().st_size==item['size'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],name
dest=root/'.tmp/sqlite-numpy-r7-rootverify-20261015';assert not dest.exists()
shutil.copytree(src,dest)
source=dest/'source'
before={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['store.py','test_store.py','pyproject.toml','uv.lock']}
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
python=root/'.tmp/sqlite-numpy-r7-20261015/.venv/Scripts/python.exe'
command=[str(python),'-B','-X','utf8','-m','unittest','-v','test_store']
run=subprocess.run(command,cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
(dest/'root-tests.stdout.log').write_text(run.stdout,encoding='utf-8');(dest/'root-tests.stderr.log').write_text(run.stderr,encoding='utf-8')
assert before=={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in before}
lock=tomllib.loads((source/'uv.lock').read_text(encoding='utf-8'))
expected={p['name']:p['version'] for p in lock['package'] if p.get('source',{}).get('registry')}
assert expected=={'numpy':'2.5.4'}
identity_code="import importlib.metadata,json,sqlite3,sys,numpy; print(json.dumps({'python':sys.version,'base_prefix':sys.base_prefix,'sqlite':sqlite3.sqlite_version,'numpy':numpy.__version__,'installed':{d.metadata['Name'].lower():d.version for d in importlib.metadata.distributions()}}))"
identity=subprocess.run([str(python),'-B','-c',identity_code],cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
assert identity.returncode==0,identity.stderr
data=json.loads(identity.stdout);assert data['sqlite']=='3.54.0' and data['numpy']=='2.5.4' and data['installed']==expected
assert Path(data['base_prefix']).resolve()==(root/'.tmp/sqlite-runtime-r7-20261015/derived/python').resolve()
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frozen_manifest_sha256':mh,'frozen_files_verified':len(m),'command':command,'cwd':str(source),'exit_code':run.returncode,'source_before':before,'source_after':before,'identity':data,'lock_packages':expected,'scope':'root copied final source actual author tests; independent reviewer fixtures separate; no production coverage or deployment'}
(dest/'root-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(run.stdout+run.stderr,flush=True);print(json.dumps(receipt),flush=True)
raise SystemExit(run.returncode)
