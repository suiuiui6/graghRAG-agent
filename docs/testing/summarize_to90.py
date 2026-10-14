"""Summarize raw evidence; never turn unresolved security into a passing gate."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/testing'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def ratio(covered, total):
    return {'covered': covered, 'total': total, 'percent': covered * 100 / total,
            'passed': covered * 10 >= total * 9}


def main():
    prefix = 'docs/testing/2026-10-13-to90-final-r2'
    before = read(prefix + '-inputs-before.json')
    after = read(prefix + '-inputs-after.json')
    coverage = read(prefix + '-coverage.json')
    totals = coverage['totals']
    backend_inputs = after['sha256']
    backend_drift = [name for name, digest in backend_inputs.items()
                     if not (ROOT / name).is_file()
                     or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    frontend_manifest = read('docs/testing/frontend-widget-upload-20261013/input-manifest.json')
    frontend_drift = [entry['path'] for entry in frontend_manifest
                      if not (ROOT / entry['path']).is_file()
                      or hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest() != entry['sha256']]
    frontend = read('docs/testing/frontend-widget-upload-20261013/coverage/coverage-summary.json')['total']
    eval_totals = read('docs/testing/rag-eval-readiness-20261013/coverage.json')['totals']
    eval_snapshot = read('docs/testing/rag-eval-readiness-20261013/snapshot-after.json')
    eval_root = ROOT / 'iteration-2/eval-2-existing-components/rag_eval'
    eval_drift = [name for name, digest in eval_snapshot['inputs'].items()
                  if not (eval_root / name).is_file()
                  or hashlib.sha256((eval_root / name).read_bytes()).hexdigest() != digest]
    audit = read('docs/testing/2026-10-13-to90-wave3-pip-audit.json')
    findings = [dict(package=dep['name'], version=dep['version'], **vuln)
                for dep in audit['dependencies'] for vuln in dep['vulns']]
    report = {
        'overall': 'BLOCKED_SECURITY_AND_RELEASE_VALIDATION',
        'execution_mode': 'audit-only-windows',
        'backend': {
            'production_files': len(coverage['files']),
            'pytest_exit': int((ROOT / (prefix + '-exit.txt')).read_text(encoding='utf-8-sig')),
            'coverage_export_exit': int((ROOT / (prefix + '-export-exit.txt')).read_text(encoding='utf-8-sig')),
            'lines': ratio(totals['covered_lines'], totals['num_statements']),
            'branches': ratio(totals['covered_branches'], totals['num_branches']),
            'snapshot_stable': before['sha256'] == after['sha256'],
            'protected_artifacts_stable': before['protected_artifacts_sha256'] == after['protected_artifacts_sha256'],
            'current_input_drift': backend_drift,
            'snapshot_sha256': after['snapshot_sha256'],
        },
        'frontend': {
            'production_files': 29,
            'lines': ratio(frontend['lines']['covered'], frontend['lines']['total']),
            'branches': ratio(frontend['branches']['covered'], frontend['branches']['total']),
            'current_input_drift': frontend_drift,
        },
        'rag_eval': {
            'production_files': 12,
            'lines': ratio(eval_totals['covered_lines'], eval_totals['num_statements']),
            'branches': ratio(eval_totals['covered_branches'], eval_totals['num_branches']),
            'evidence': 'docs/testing/rag-eval-readiness-20261013/',
            'current_input_drift': eval_drift,
        },
        'backend_dependency_findings': findings,
        'limitations': [
            'Chroma advisories have not been patched; no vulnerability ignores were added.',
            'Research freeze drift remains a separate failed experiment-admission gate.',
            'Real provider acceptance, Docker images and remote CI/protection have not been verified.',
            'Independent local review passed its recorded scope; it does not replace release acceptance.',
        ],
        'committed': False, 'pushed': False, 'deployed': False,
    }
    (OUT / '2026-10-13-to90-summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('overall', 'backend', 'frontend', 'rag_eval')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
