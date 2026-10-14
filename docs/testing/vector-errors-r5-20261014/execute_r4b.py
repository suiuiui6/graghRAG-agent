import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root.parents[1]
phase=sys.argv[1]
lance=repo/'.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe'
chroma=repo/'.tmp/backend-quality-venv-20261012/Scripts/python.exe'
jobs = [(chroma,'wide_matrix.py',['chroma','oracle']),(lance,'wide_matrix.py',['lance','red'])] if phase=='red' else [(lance,'wide_matrix.py',['lance','green']),(lance,'run_checks.py',['final']),(lance,'ingress_matrix.py',['green']),(chroma,'fresh_matrix.py',['chroma']),(lance,'fresh_matrix.py',['lance'])]
inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.suffix in ('.py','.md')}
commands=[]
for python,script,args in jobs:
    command=[str(python),str(root/script),*args]
    run=subprocess.run(command,capture_output=True,text=True,timeout=240)
    name=phase+'-'+script+'-'+('-'.join(args))
    (root/(name+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    (root/(name+'.exit')).write_text(str(run.returncode))
    commands.append({'command':command,'exit_code':run.returncode})
    print(name,run.returncode,run.stdout[-500:],flush=True)
assert inputs=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.suffix in ('.py','.md')}
(root/(phase+'-execution-manifest.json')).write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'inputs':inputs,'unchanged':True,'commands':commands},indent=2))
if phase!='red': raise SystemExit(any(x['exit_code'] for x in commands))
