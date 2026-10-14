import hashlib,json,subprocess,sys,shutil
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root.parents[1]
dest=repo/'docs/testing/vector-ingress-r4-20261014'
inputs=[p for p in root.iterdir() if p.is_file() and p.suffix in ('.py','.md')]+[root/'fixtures.json',root/'numeric-oracle.json',root/'fresh-chroma.json']
hashes=lambda:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
before=hashes(); commands=[]
for script,args in [('ingress_matrix.py',['green']),('fresh_matrix.py',['lance'])]:
    command=[sys.executable,str(root/script),*args]
    result=subprocess.run(command,capture_output=True,text=True,timeout=120)
    (root/f'final-{script}.log').write_text(result.stdout+result.stderr)
    commands.append({'command':command,'exit_code':result.returncode})
assert before==hashes()
(root/'final-ingress-manifest.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'inputs':before,'unchanged':True,'commands':commands},indent=2))
if any(c['exit_code'] for c in commands): raise SystemExit(1)
dest.mkdir(exist_ok=True)
for source in root.iterdir():
    if source.is_file(): shutil.copy2(source,dest/source.name)
for sub in ['final','red-set']:
    out=dest/sub; out.mkdir(exist_ok=True)
    for source in (root/sub).iterdir():
        if source.is_file(): shutil.copy2(source,out/source.name)
manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file() and p.name!='freeze-manifest.json'}
(dest/'freeze-manifest.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'files':manifest},indent=2))
print(json.dumps({'frozen_files':len(manifest),'commands':commands}))
