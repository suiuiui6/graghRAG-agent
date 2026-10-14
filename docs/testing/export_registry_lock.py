"""Export every registry pin from the backend lock, including optional platforms."""
import hashlib
import json
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[2]
lock_path = root / 'backend/uv.lock'
packages = tomllib.loads(lock_path.read_text(encoding='utf-8'))['package']
pins = sorted({(p['name'], p['version']) for p in packages if 'registry' in p.get('source', {})})
out = root / 'docs/testing'
(out / '2026-10-13-to90-final-lock-pins.txt').write_text(
    ''.join(f'{name}=={version}\n' for name, version in pins), encoding='utf-8')
receipt = {'lock_sha256': hashlib.sha256(lock_path.read_bytes()).hexdigest(),
           'registry_pins': len(pins), 'scope': 'all registry entries, no platform/extra filtering'}
(out / '2026-10-13-to90-final-lock-export.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt))
