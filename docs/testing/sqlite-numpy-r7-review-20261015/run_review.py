import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[2]
own = Path(__file__).resolve().parent
archive = root/'docs/testing/sqlite-numpy-r7-final-20261015'
manifest = json.loads((archive/'manifest.json').read_text(encoding='utf-8-sig'))
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(archive/'manifest.json') == 'fcf0ecf3cbf8c5a57ceb98d970333a7c54f9de09ab5ec6951d2fcbfeab41fc2d'
for name, identity in manifest.items():
    path = archive/name
    assert path.stat().st_size == identity['size'] and digest(path) == identity['sha256'], name
private = own/'private-final'
private.mkdir(exist_ok=True)
for path in (archive/'source').glob('*'):
    if path.is_file():
        shutil.copyfile(path, private/path.name)
shutil.copyfile(own/'test_independent.py', private/'test_independent.py')
before = {p.name:digest(p) for p in private.iterdir() if p.is_file()}
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONPATH=str(private))
commands = []
for label, module in [('author-nine','test_store'),('independent-new','test_independent')]:
    command = [sys.executable,'-X','utf8','-m','unittest',module,'-v']
    started = time.time()
    result = subprocess.run(command,cwd=private,env=environment,capture_output=True,text=True,timeout=180)
    (own/(label+'.stdout.log')).write_text(result.stdout,encoding='utf-8')
    (own/(label+'.stderr.log')).write_text(result.stderr,encoding='utf-8')
    commands.append(dict(label=label,command=command,cwd=str(private),exit_code=result.returncode,
                         started=started,elapsed=time.time()-started))
after = {p.name:digest(p) for p in private.iterdir() if p.is_file()}
report = dict(manifest_verified=len(manifest),manifest_sha256=digest(archive/'manifest.json'),
              input_before=before,input_after=after,input_drift=before!=after,commands=commands)
(own/'review-receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
assert before==after and all(item['exit_code']==0 for item in commands)
