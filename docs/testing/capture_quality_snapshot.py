"""Hash audit inputs without reading credentials or generated runtime data."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'.venv', 'tests', 'output', 'uploads', '__pycache__', 'node_modules'}


def production_files():
    return sorted(p for p in (ROOT / 'backend').rglob('*.py')
                  if not any(part in EXCLUDED for part in p.relative_to(ROOT / 'backend').parts)
                  and not ('research' in p.relative_to(ROOT / 'backend').parts
                           and p.name.startswith('test_')))


def main():
    production = production_files()
    tests = sorted(p for p in (ROOT / 'backend/tests').rglob('test_*.py')
                   if '_sandbox_tmp' not in p.parts)
    inputs = production + tests + [ROOT / p for p in (
        'backend/research/test_deepseek_scope_pilot.py', 'backend/tests/conftest.py',
        'backend/pyproject.toml', 'backend/uv.lock', 'backend/requirements.txt',
        'frontend/package.json', 'frontend/pnpm-lock.yaml', 'frontend/.nvmrc',
        'docs/testing/coverage-backend-2026-10-12.ini',
        'Dockerfile.backend', 'Dockerfile.frontend', '.dockerignore', '.github/workflows/ci.yml')]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(set(inputs)) if p.is_file()}
    report = {'time_utc': datetime.now(timezone.utc).isoformat(),
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'production_files': [p.relative_to(ROOT).as_posix() for p in production],
              'sha256': hashes}
    protected = ['backend/output/runtime/bm25_artifact.json',
                 'backend/output/runtime/table_artifact.json',
                 'backend/output/docs_store.json', 'backend/output/vectordb/chroma.sqlite3']
    report['protected_artifacts_sha256'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() if (ROOT / name).is_file() else None
        for name in protected}
    report['snapshot_sha256'] = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    Path(sys.argv[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'production_files': len(production), 'inputs': len(hashes),
                      'snapshot_sha256': report['snapshot_sha256']}))


if __name__ == '__main__':
    main()
