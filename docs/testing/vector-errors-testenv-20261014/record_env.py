import hashlib
import importlib.metadata as md
import json
import sys
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parent
lock = tomllib.loads((root / 'uv.lock').read_text())
expected = {p['name']: p['version'] for p in lock['package'] if 'registry' in p.get('source', {})}
norm = lambda s: s.lower().replace('_', '-')
actual = {norm(d.metadata['Name']): d.version for d in md.distributions()}
assert expected == actual, {'expected': expected, 'actual': actual}
pins = json.loads((root / 'runtime-pins.json').read_text())
assert all(actual[k] == v for k, v in pins.items())
assert set(actual) - set(pins) == {'structlog'}
audit = json.loads((root / 'pip-audit.json').read_text())
assert len(audit['dependencies']) == 18
assert not [d for d in audit['dependencies'] if d['vulns']]
receipt = {'python': sys.version, 'executable': sys.executable,
           'registry_locked': len(expected), 'installed': actual,
           'runtime_pins': len(pins), 'test_only': ['structlog'],
           'drift': [], 'pypi_audit_findings': 0,
           'native_security': 'NOT_COVERED_BY_PYPI_AUDIT',
           'lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest()}
(root / 'environment-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
target = root.parents[1] / 'docs/testing/vector-errors-testenv-20261014'
assert not target.exists()
target.mkdir()
files = {}
for item in root.iterdir():
    if item.is_file():
        data = item.read_bytes()
        (target / item.name).write_bytes(data)
        files[item.name] = hashlib.sha256(data).hexdigest()
(target / 'manifest.json').write_text(json.dumps({'files': files}, indent=2), encoding='utf-8')
print(json.dumps({'locked_installed': len(actual), 'drift': [], 'audit_findings': 0, 'evidence_files': len(files)}))
