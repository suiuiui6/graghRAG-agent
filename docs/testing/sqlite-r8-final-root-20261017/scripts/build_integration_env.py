from pathlib import Path
import json,subprocess,os
r=Path('D:/graghRAG-agent');e=r/'.tmp/sqlite-r8-integration-env-20261017';e.mkdir(exist_ok=True)
deps=json.loads((r/'.tmp/sqlite-r8-root-20261016/consumer-import-packages.json').read_text());deps.pop('chromadb');deps['numpy']='2.5.4';deps['duckdb']='1.5.5'
(e/'pyproject.toml').write_text('[project]\nname="sqlite-r8-consumer-integration"\nversion="0.0.1"\nrequires-python="==3.12.*"\ndependencies='+json.dumps([k+'=='+v for k,v in sorted(deps.items())])+'\n[tool.uv]\npackage=false\n',encoding='utf8')
uv='D:/Python/Scripts/uv.exe';env=dict(os.environ,UV_CACHE_DIR=str(e/'uv-cache'),PYTHONDONTWRITEBYTECODE='1')
commands=[[uv,'venv','.venv','--python',str(r/'.tmp/sqlite-runtime-r7-20261015/derived/python/python.exe'),'--no-python-downloads'],[uv,'lock','--index-url','https://pypi.org/simple'],[uv,'sync','--frozen','--no-python-downloads']]
receipts=[]
for i,c in enumerate(commands):
 p=subprocess.run(c,cwd=e,env=env,capture_output=True,text=True,encoding='utf8');(e/f'{i}.log').write_text(p.stdout+p.stderr,encoding='utf8');receipts.append({'command':c,'exit_code':p.returncode});(e/'setup-receipt.json').write_text(json.dumps(receipts,indent=2),encoding='utf8');print(i,p.returncode,flush=True)
 if p.returncode:print(p.stderr[-1800:],flush=True);break
raise SystemExit(receipts[-1]['exit_code'])
