"""Freeze isolated inputs and replay final offline probes; preserve failures."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
repo = root.parents[2]
dest = repo / 'docs/testing/vector-replacement-r2-20261014'
dest.mkdir(parents=True, exist_ok=True)
inputs = list(root.glob('*.py')) + [root/'fixtures.json', root.parent/'uv.lock', root.parent/'pyproject.toml']
def hashes():
    return {str(p.relative_to(repo)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
before = hashes()
commands = []
for name, python, script, args in [
    ('original76', root.parent/'.venv/Scripts/python.exe', 'lance_truth.py', []),
    ('boundary_chroma', repo/'.tmp/backend-quality-venv-20261012/Scripts/python.exe', 'boundary_probe.py', ['chroma']),
    ('boundary_lance', root.parent/'.venv/Scripts/python.exe', 'boundary_probe.py', ['lance']),
]:
    command = [str(python), str(root/script), *args]
    with (dest/f'{name}.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    (dest/f'{name}.exit').write_text(str(result.returncode), encoding='ascii')
    commands.append({'command': command, 'exit_code': result.returncode})
after = hashes()
assert before == after
for path in root.iterdir():
    if path.is_file() and (path.suffix in ['.py', '.json', '.log', '.exit'] or path.name.endswith('.l2-history')):
        shutil.copy2(path, dest/path.name)
manifest = {'utc': datetime.now(timezone.utc).isoformat(), 'inputs_before': before, 'inputs_after': after, 'unchanged': before == after, 'commands': commands, 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.iterdir()) if p.is_file() and p.name != 'freeze-manifest.json'}}
(dest/'freeze-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'unchanged': before == after, 'commands': commands}))
