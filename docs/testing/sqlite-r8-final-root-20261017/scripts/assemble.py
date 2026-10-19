from pathlib import Path
import hashlib,json,shutil,subprocess,os
r=Path('D:/graghRAG-agent');out=r/'.tmp/sqlite-r8-combined-20261017';out.mkdir(exist_ok=False)
inputs=[]
for folder,sub in [('sqlite-r8-consumers-r2-20261017','source/backend'),('sqlite-vector-r8-20261017','backend')]:
 s=r/'docs/testing'/folder;m=json.loads((s/'manifest.json').read_text())
 for n,v in m.items():assert hashlib.sha256((s/n).read_bytes()).hexdigest()==(v if type(v)is str else v['sha256']),n
 inputs.append({'archive':folder,'files':len(m),'manifest_sha256':hashlib.sha256((s/'manifest.json').read_bytes()).hexdigest()})
 shutil.copytree(s/sub,out/'backend',dirs_exist_ok=True)
shutil.copytree(r/'docs/testing/sqlite-vector-r8-20261017/tests',out/'adapter-tests')
(out/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf8')
p=r/'.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe'
c=[str(p),'-B','-X','utf8','-m','pytest',str(out/'backend/tests'),str(out/'adapter-tests'),'-q','-p','no:cacheprovider']
env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',GRAPHRAG_RUNTIME_ARTIFACTS_DIR=str(out/'artifacts'))
res=subprocess.run(c,cwd=out,env=env,capture_output=True,text=True,encoding='utf8')
(out/'tests.stdout.log').write_text(res.stdout,encoding='utf8');(out/'tests.stderr.log').write_text(res.stderr,encoding='utf8');(out/'receipt.json').write_text(json.dumps({'command':c,'cwd':str(out),'exit_code':res.returncode,'inputs':inputs},indent=2),encoding='utf8');print(res.stdout[-2500:]);print('exit',res.returncode)
