import os,subprocess,json,hashlib,sys
from pathlib import Path
r=Path(__file__).resolve().parent;repo=r.parents[1];lance=repo/'.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe';chroma=repo/'.tmp/backend-quality-venv-20261012/Scripts/python.exe'
env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1')
env.update(TRANSFORMERS_OFFLINE='1',ANONYMIZED_TELEMETRY='False')
inputs=list(r.glob('*.py'))+list((r/'current-consumer').glob('*.py'))+[repo/'.tmp/vector-errors-testenv-20261014/uv.lock',repo/'backend/uv.lock']
def hashes():return {str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
before=hashes()
jobs=[('original76',lance,'lance_truth.py',[]),('boundary_chroma',chroma,'boundary_probe.py',['chroma']),('boundary_lance',lance,'boundary_probe.py',['lance']),('matrix_chroma',chroma,'numeric_matrix.py',['chroma']),('matrix_lance',lance,'numeric_matrix.py',['lance']),('wide_chroma',chroma,'wide_matrix.py',['chroma','oracle']),('wide_lance',lance,'wide_matrix.py',['lance','green']),('ingress',lance,'ingress_matrix.py',['green']),('fresh_chroma',chroma,'fresh_matrix.py',['chroma']),('fresh_lance',lance,'fresh_matrix.py',['lance']),('facade',lance,'test_facade.py',[]),('r6',lance,'test_r6.py',[])]
jobs += [('errors',lance,'test_errors.py',[]),('new_record_chroma',chroma,'fresh_wide_record.py',['chroma']),('new_record_lance',lance,'fresh_wide_record.py',['lance'])]
receipts=[]
for name,python,script,args in jobs:
 command=[str(python),str(r/script),*args];proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=240)
 prefix='resume-r6-'
 (r/f'{prefix}{name}.log').write_text(proc.stdout+proc.stderr,encoding='utf-8');(r/f'{prefix}{name}.exit').write_text(str(proc.returncode))
 receipts.append({'name':name,'command':command,'exit_code':proc.returncode});print(name,proc.returncode,(proc.stdout+proc.stderr)[-800:],flush=True)
after=hashes()
(r/'resume-r6-regressions.json').write_text(json.dumps({'inputs_before':before,'inputs_after':after,'unchanged':before==after,'commands':receipts},indent=2));sys.exit(any(x['exit_code'] for x in receipts) or before!=after)
