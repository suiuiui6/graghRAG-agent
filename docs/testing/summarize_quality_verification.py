"""Summarize immutable tool outputs; never modify coverage or audit reports."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/testing'
PREFIX = sys.argv[1] if len(sys.argv) > 1 else '2026-10-13-quality-verified'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


before = read(f'{PREFIX}-inputs-before.json')
after = read(f'{PREFIX}-inputs-after.json')
coverage = read(f'{PREFIX}-backend-coverage.json')
totals = coverage['totals']
actual = {p.replace('\\', '/') for p in coverage['files']}
expected = set(before['production_files'])
audit = read('2026-10-13-candidate-pip-audit.json')
vulnerable = [p for p in audit['dependencies'] if p['vulns']]
bandit = read('2026-10-13-quality-final-bandit.json')
log = (OUT / f'{PREFIX}-backend.log').read_text(encoding='utf-8', errors='replace')
summary = {'status': 'BLOCKED', 'snapshot_sha256': after['snapshot_sha256'],
           'source_and_test_snapshot_unchanged': before['sha256'] == after['sha256'],
           'production_file_count': len(expected),
           'coverage_scope_exact_match': actual == expected,
           'coverage_missing_files': sorted(expected - actual),
           'coverage_unexpected_files': sorted(actual - expected),
           'excluded_lines': totals['excluded_lines'],
           'pytest_exit': int((OUT / f'{PREFIX}-backend-exit.txt').read_text()),
           'coverage_export_exit': int((OUT / f'{PREFIX}-coverage-export-exit.txt').read_text()),
           'pytest_summary': re.findall(r'^.*\d+ passed.*$', log, re.M)[-1:],
           'coverage': {},
           'candidate_dependency_metadata': read('2026-10-13-candidate-dependency-metadata.json'),
           'installed_audit': {'affected_packages': len(vulnerable),
                               'raw_records': sum(len(p['vulns']) for p in vulnerable),
                               'unique_ids': sorted({v['id'] for p in vulnerable for v in p['vulns']}),
                               'packages': vulnerable},
           'bandit': {'findings': len(bandit['results']), 'metrics': bandit['metrics']['_totals'],
                      'errors': bandit['errors']},
           'research_production_integrity': read('2026-10-13-research-production-integrity.json'),
           'frontend_coverage': 'NOT_MEASURED', 'other_subprojects_coverage': 'NOT_MEASURED',
           'enforcement': 'audit-only-windows', 'commit_push_deploy': 'NOT_EXECUTED'}
for name, covered_key, total_key in [('line', 'covered_lines', 'num_statements'),
                                      ('branch', 'covered_branches', 'num_branches')]:
    covered, total = totals[covered_key], totals[total_key]
    summary['coverage'][name] = {'covered': covered, 'total': total, 'percent': covered / total * 100,
                                 'passes_90_percent': covered * 10 >= total * 9,
                                 'additional_covered_needed_at_current_denominator': max(0, (total * 9 + 9) // 10 - covered)}
summary['largest_remaining_gaps'] = [
    {'file': p, 'missing_lines': f['summary']['missing_lines'],
     'missing_branches': f['summary']['missing_branches']}
    for p, f in sorted(coverage['files'].items(), key=lambda item: item[1]['summary']['missing_lines'], reverse=True)[:15]]
(OUT / f'{PREFIX}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: summary[k] for k in ('status', 'source_and_test_snapshot_unchanged',
                 'production_file_count', 'coverage_scope_exact_match', 'pytest_summary', 'coverage')}, ensure_ascii=False))
