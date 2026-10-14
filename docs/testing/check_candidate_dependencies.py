"""Record installed candidate metadata against the lock, without importing packages."""
import importlib.metadata as metadata
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/testing'


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


lock = tomllib.loads((ROOT / 'backend/uv.lock').read_text(encoding='utf-8'))
locked = {normalize(p['name']): p for p in lock['package']}
installed = {normalize(d.metadata['Name']): d.version for d in metadata.distributions()}
drift = {n: {'installed': v, 'locked': locked.get(n, {}).get('version')}
         for n, v in installed.items() if n not in locked or v != locked[n].get('version')}
registry = {n: v for n, v in sorted(installed.items()) if 'registry' in locked.get(n, {}).get('source', {})}
report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'installed_count': len(installed),
          'installed': installed, 'registry_count': len(registry), 'version_drift': drift,
          'lock_not_installed': sorted(set(locked) - set(installed)),
          'note': 'Platform/optional lock entries need not be installed; every installed version must match.'}
(OUT / '2026-10-13-candidate-dependency-metadata.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(OUT / '2026-10-13-candidate-registry-pins.txt').write_text(''.join(f'{n}=={v}\n' for n, v in registry.items()), encoding='utf-8')
print(json.dumps({'installed': len(installed), 'registry': len(registry), 'drift': drift}))
raise SystemExit(bool(drift))
