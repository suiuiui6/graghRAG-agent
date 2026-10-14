import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
source = repo / 'docs/testing/vector-errors-r5-20261014'
manifest_file = source / 'r5-freeze-manifest.json'
manifest = json.loads(manifest_file.read_text())
for name, digest in manifest['files'].items():
    path = (source / name).resolve()
    assert path.is_relative_to(source.resolve())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
target = repo / '.tmp/vector-errors-r5-rootverify-20261014'
assert not target.exists()
shutil.copytree(source, target)
core = ['vector_errors.py', 'generic_filter.py', 'parser_port.py', 'probe_store.py', 'test_errors.py', 'test_facade.py']
before = {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in core}
commands = []
for script in ['test_errors.py', 'test_facade.py']:
    command = [sys.executable, str(target / script)]
    run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=240)
    (target / ('root-' + script + '.log')).write_text(run.stdout + run.stderr, encoding='utf-8')
    commands.append({'command': command, 'exit_code': run.returncode})
    print(script, run.returncode, run.stdout[-200:], run.stderr[-450:], flush=True)
assert before == {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in core}
receipt = {'utc': datetime.now(timezone.utc).isoformat(),
           'source_freeze_sha256': hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
           'frozen_files_verified': len(manifest['files']), 'core': before,
           'commands': commands, 'scope': 'root copied final snapshot, not independent reviewer'}
(target / 'root-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
raise SystemExit(any(x['exit_code'] for x in commands))
