import os,sys,json,hashlib,subprocess,datetime
from pathlib import Path
r=Path(__file__).resolve().parents[2]; o=Path(__file__).parent
py=r/'.tmp/backend-quality-venv-20261012/Scripts/python.exe'
def snap():
    paths=[]
    for base,dirs,files in os.walk(r/'backend'):
        dirs[:]=[d for d in dirs if d not in ('.venv','__pycache__','output','uploads','node_modules') and not (Path(base)==r/'backend/tests' and d.startswith(('_sandbox_','_tmp_','tmp_basetemp_','tmp_probe_')))]
        paths.extend(Path(base)/f for f in files if f.endswith('.py'))
    paths += [r/'backend/pyproject.toml',r/'backend/uv.lock',r/'docs/testing/coverage-backend-2026-10-12.ini']
    return {str(p.relative_to(r)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
before=snap(); (o/'before.json').write_text(json.dumps(before,indent=2))
env=dict(os.environ,PYTHONPATH=str(r/'.tmp/coverage-runtime-py312-20261012')+os.pathsep+str(r/'langextract')+os.pathsep+str(r/'backend'),PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',ANONYMIZED_TELEMETRY='False')
commands=[]
def run(name,args,timeout=1200):
    with (o/(name+'.log')).open('w',encoding='utf-8') as f:
        try: code=subprocess.run(args,cwd=r,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired: code=124
    commands.append(dict(name=name,command=args,exit=code)); (o/'commands.json').write_text(json.dumps(commands,indent=2)); return code
run('tests',[str(py),'-m','coverage','run','--rcfile=docs/testing/coverage-backend-2026-10-12.ini','--data-file='+str(o/'backend.coverage'),'-m','pytest','backend/tests','backend/research/test_deepseek_scope_pilot.py','-q','--tb=short','-p','no:cacheprovider','--basetemp',str(o/'test-temp')])
run('export',[str(py),'-m','coverage','json','--rcfile=docs/testing/coverage-backend-2026-10-12.ini','--data-file='+str(o/'backend.coverage'),'-o',str(o/'coverage.json')])
after=snap(); (o/'after.json').write_text(json.dumps(after,indent=2))
cov=json.loads((o/'coverage.json').read_text()); t=cov['totals']
production=[p for p in before if p.endswith('.py') and not '/tests/' in p and not '/research/test_' in p]
actual=[p.replace('\\','/') for p in cov['files']]
summary=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=commands,inputs_stable=before==after,production_count=len(production),coverage_count=len(actual),missing=sorted(set(production)-set(actual)),extra=sorted(set(actual)-set(production)),totals=t)
(o/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))

sys.exit(0 if all(c['exit']==0 for c in commands) else 1)

