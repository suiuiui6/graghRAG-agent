import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
repo = root.parents[1]
phase = sys.argv[1]
dest = root / phase
dest.mkdir(exist_ok=True)
lance = repo / '.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe'
chroma = repo / '.tmp/backend-quality-venv-20261012/Scripts/python.exe'
inputs = list(root.glob('*.py')) + [root/'fixtures.json', root/'chroma-truth-1791897325903702500.json', repo/'.tmp/vector-replacement-mvp-20261013/uv.lock', repo/'backend/uv.lock', repo/'docs/contracts/2026-10-14-vector-numeric-semantics.md']
def hashes(): return {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
before = hashes()
commands = []
for name, python, script, args in [
    ('original76', lance, 'lance_truth.py', []),
    ('boundary_chroma', chroma, 'boundary_probe.py', ['chroma']),
    ('boundary_lance', lance, 'boundary_probe.py', ['lance']),
    ('matrix_chroma', chroma, 'numeric_matrix.py', ['chroma']),
    ('matrix_lance', lance, 'numeric_matrix.py', ['lance']),
]:
    command = [str(python), str(root/script), *args]
    with (dest/f'{name}.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    (dest/f'{name}.exit').write_text(str(result.returncode))
    commands.append({'command': command, 'exit_code': result.returncode})
after = hashes()
assert before == after
for path in root.iterdir():
    if path.is_file() and path.suffix in ('.py', '.json'): shutil.copy2(path, dest/path.name)
manifest = {'utc': datetime.now(timezone.utc).isoformat(), 'phase': phase, 'inputs_before': before, 'inputs_after': after, 'unchanged': before==after, 'commands': commands}
(dest/'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(commands))
raise SystemExit(any(c['exit_code'] != 0 for c in commands))
