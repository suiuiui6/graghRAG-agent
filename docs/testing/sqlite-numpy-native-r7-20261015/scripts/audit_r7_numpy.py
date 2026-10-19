import datetime,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-numpy-native-audit-20261015';out.mkdir(exist_ok=True)
req=out/'audit-requirements.txt';req.write_text('numpy==2.5.4\n',encoding='utf-8')
command=[str(root/'.tmp/audit-tools-20261012/Scripts/python.exe'),'-m','pip_audit','-r',str(req),'--no-deps','--disable-pip','--strict','--index-url','https://pypi.org/simple','--cache-dir',str(out/'audit-http-cache'),'--timeout','30','--progress-spinner','off','-f','json','-o',str(out/'pip-audit.json')]
result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
(out/'pip-audit.log').write_text(result.stdout+result.stderr,encoding='utf-8');(out/'pip-audit.exit').write_text(str(result.returncode),encoding='utf-8')
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'exit_code':result.returncode,'requirements_sha256':hashlib.sha256(req.read_bytes()).hexdigest(),'scope':'One fully pinned registry dependency; installed lock identity checked separately. Does not audit CPython/SQLite DLL/OpenBLAS/Windows runtimes.'}
(out/'pip-audit-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
raise SystemExit(result.returncode)
