import hashlib,json,os,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-runtime-r7-20261015'
base=out/'runtime';derived=out/'derived';assert not derived.exists()
sql=out/'sqlite-official/sqlite3.dll'
sr=json.loads((out/'sqlite-official/sqlite-artifact-receipt.json').read_text(encoding='utf-8'))
assert hashlib.sha256(sql.read_bytes()).hexdigest()==sr['dll_sha256']
def hashes(path):return {str(p.relative_to(path)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob('*')) if p.is_file()}
before=hashes(base)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1')
floor=root/'.tmp/r7_sqlite_floor.py'
red=subprocess.run([str(base/'python/python.exe'),'-B',str(floor)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
(out/'floor-red.log').write_text(red.stdout+red.stderr,encoding='utf-8');(out/'floor-red.exit').write_text(str(red.returncode),encoding='utf-8')
assert red.returncode==1
shutil.copytree(base,derived)
assert hashes(derived)==before
target=derived/'python/DLLs/sqlite3.dll'
assert target.is_file() and target.resolve().is_relative_to(derived.resolve())
shutil.copyfile(sql,target)
after=hashes(derived)
changes=[n for n in sorted(set(before)|set(after)) if before.get(n)!=after.get(n)]
assert changes==['python/DLLs/sqlite3.dll'],changes
assert hashes(base)==before
receipt={'kind':'project-derived isolated combination, not unmodified official Python distribution','official_python_artifact_receipt_sha256':hashlib.sha256((out/'artifact-receipt.json').read_bytes()).hexdigest(),'official_sqlite_artifact_receipt_sha256':hashlib.sha256((out/'sqlite-official/sqlite-artifact-receipt.json').read_bytes()).hexdigest(),'base_files':before,'derived_files':after,'changed_files':changes,'base_unchanged':True,'base_floor_exit':red.returncode}
(out/'derived-composition.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
green=subprocess.run([str(derived/'python/python.exe'),'-B',str(floor)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
(out/'floor-green.log').write_text(green.stdout+green.stderr,encoding='utf-8');(out/'floor-green.exit').write_text(str(green.returncode),encoding='utf-8')
print(green.stdout,flush=True)
assert green.returncode==0,green.stderr
probe_text=(out/'probe.py').read_text(encoding='utf-8').replace("out = pathlib.Path(__file__).resolve().parent","out = pathlib.Path(__file__).resolve().parent / 'derived-evidence'; out.mkdir(exist_ok=True)")
probe=out/'derived_probe.py';probe.write_text(probe_text,encoding='utf-8')
run=subprocess.run([str(derived/'python/python.exe'),'-B',str(probe)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=60)
(out/'derived-probe.log').write_text(run.stdout+run.stderr,encoding='utf-8');(out/'derived-probe.exit').write_text(str(run.returncode),encoding='utf-8')
print(run.stdout,flush=True)
assert run.returncode==0,run.stderr
r=json.loads((out/'derived-evidence/runtime-native.json').read_text(encoding='utf-8'))
assert r['sqlite_floor_met'] and r['sqlite_version']=='3.54.0'
loaded=[x for x in r['loaded_modules'] if Path(x['path']).name.lower()=='sqlite3.dll']
assert len(loaded)==1 and Path(loaded[0]['path']).resolve()==target.resolve() and loaded[0]['sha256']==sr['dll_sha256']
assert hashes(base)==before
assert hashes(derived)==after
print(json.dumps({'profile':str(derived/'python/python.exe'),'base_unchanged':True,'changed_files':changes,'actual_sqlite':r['sqlite_version'],'actual_loaded_sqlite_sha256':loaded[0]['sha256']}))
