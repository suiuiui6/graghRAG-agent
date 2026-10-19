import hashlib,json,os,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent.parent
src=root/'docs/testing/vector-r6-20261014'
mf=src/'r6-freeze-manifest.json'
manifest=json.loads(mf.read_text(encoding='utf-8'))
assert hashlib.sha256(mf.read_bytes()).hexdigest()=='37a4ca29ce343e1621235b1bb8fdbee52beb120b67134fc3b32d1e6c1d1fbac5'
for name,digest in manifest['files'].items():
    path=(src/name).resolve();assert path.is_relative_to(src.resolve())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
dest=root/'.tmp/vector-r6-root-run-20261015';assert not dest.exists()
shutil.copytree(src,dest)
core=['generic_filter.py','probe_store.py','parser_port.py','vector_errors.py','safe_vector_logging.py','test_r6.py','test_errors.py','test_facade.py','fresh_wide_record.py']
before={n:hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in core}
env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
commands=[]
for script,args in [('test_r6.py',[]),('test_errors.py',[]),('test_facade.py',[]),('fresh_wide_record.py',['lance'])]:
    command=[sys.executable,str(dest/script),*args]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=240)
    (dest/('root-'+script+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    commands.append({'command':command,'exit_code':result.returncode})
    print(script,result.returncode,(result.stdout+result.stderr)[-500:],flush=True)
after={n:hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in core}
assert before==after
receipt={'utc':datetime.now(timezone.utc).isoformat(),'freeze_sha256':hashlib.sha256(mf.read_bytes()).hexdigest(),'frozen_files_verified':len(manifest['files']),'core_before':before,'core_after':after,'commands':commands,'scope':'root reruns copied author final snapshot; independent reviewer tests separate'}
(dest/'root-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
raise SystemExit(any(x['exit_code'] for x in commands))
