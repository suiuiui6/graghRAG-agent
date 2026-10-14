"""Offline entry-point contracts; not a model experiment."""
import importlib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def tool():
    assert (ROOT / 'backend/research/local_scope_v2.py').exists(), 'offline CLI not implemented'
    return importlib.import_module('backend.research.local_scope_v2')


def test_check_summary_no_private_text():
    report = tool().check_package(ROOT)
    assert report['status'] == 'LOCAL_SOURCE_BINDING_PASS'
    assert report['counts']['questions'] == 9
    assert report['human_certified'] is False
    assert report['api_execution'] == 'NOT_EXECUTED'
    assert 'exact_text' not in json.dumps(report)


def test_b0_preparation_is_not_execution():
    report = tool().prepare_b0(ROOT)
    assert report['status'] == 'BLOCKED_NOT_EXECUTED'
    assert report['arms'] == ['B0_NATIVE', 'C_NATIVE_CONTEXT', 'C_AUTO_SCOPE', 'C_ORACLE_SCOPE']
    # Software must report drift faithfully; research admission is a separate
    # nonzero gate. The immutable historical freeze is not rewritten for fixes.
    frozen = json.loads((ROOT / 'docs/superpowers/plans/scope-pilot/gold-review-v2/local-freeze-v2-20261008.json')
                        .read_text(encoding='utf-8'))['production_files_sha256']
    records = report['production_integrity']['files']
    assert frozen and set(records) == set(frozen)
    comparisons = []
    for path, expected in frozen.items():
        file = ROOT / path
        actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
        assert records[path] == {'expected': expected, 'actual': actual, 'match': actual == expected}
        comparisons.append(actual == expected)
    matched = all(comparisons)
    assert report['production_integrity']['all_match_freeze'] is matched
    assert report['gates']['on_disk_production_freeze'] == ('PASS' if matched else 'DRIFT_REQUIRES_REVIEW')
    assert len(report['questions']) == 9
    assert all(q['source_selection'] == 'SOURCE_UNRESOLVED' for q in report['questions'])
    assert report['gates']['runtime_identity'] == 'UNKNOWN'
    assert report['gates']['provider_transfer_authorization'] == 'NOT_GRANTED_FOR_THIS_BATCH'
    assert report['conditional_call_proposal']['authorized'] is False
    assert report['conditional_call_proposal']['upper_bound'] == 54


@pytest.mark.parametrize('state', ['matching', 'modified', 'missing'])
def test_integrity_reports_exact_bytes_and_missing_file_without_rewriting_freeze(tmp_path, state):
    module = tool()
    file = tmp_path / 'source.py'
    original = b'original source\n'
    expected = hashlib.sha256(original).hexdigest()
    file.write_bytes(original if state == 'matching' else b'modified source\n')
    if state == 'missing':
        file.unlink()
    frozen = {'source.py': expected}
    actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.exists() else None
    result = module._integrity(tmp_path, frozen)
    assert result['files'] == {'source.py': {'expected': expected, 'actual': actual,
                                           'match': state == 'matching'}}
    assert result['all_match_freeze'] is (state == 'matching')
    assert frozen == {'source.py': expected}


def test_b0_metadata_includes_nonvector_artifacts_and_historical_guard():
    report = tool().prepare_b0(ROOT)
    assert report['historical_integrity']['all_match_freeze']
    assert len(report['historical_integrity']['files']) == 62
    assert report['local_artifact_metadata']['bm25']['records'] == 3
    assert report['local_artifact_metadata']['tables']['records'] == 2
    assert report['local_artifact_metadata']['docs_store']['runtime_loaded'] == 'UNKNOWN'


def test_explicit_source_auto_metadata_only():
    m = tool()
    report = m.auto_scope(ROOT, 'section 3.2.3', ['backend/output/mineru/ingest_f/full.md'], 8192)
    assert report['routing_status'] == 'RESOLVED'
    assert report['assembly_status'] == 'COMPLETE_SCOPE'
    assert report['mappings'][0]['start'] == 12251
    assert report['mappings'][0]['end'] == 13474
    assert 'text' not in report and 'query' not in report


def test_missing_selection_not_derived_from_gold():
    report = tool().auto_scope(ROOT, 'section 3.2.3', [], 8192)
    assert report['routing_status'] == 'SOURCE_UNRESOLVED'


def test_cli_check_fresh_process():
    tool()
    result = subprocess.run([sys.executable, '-B', '-m', 'backend.research.local_scope_v2', 'check'],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['counts']['core_items'] == 31


def test_cli_has_no_execute_and_does_not_import_production():
    module = tool()
    assert not hasattr(module, 'execute_b0')
    forbidden = {'backend.config', 'backend.retrieval', 'backend.generator', 'backend.routes.rag_query'}
    assert forbidden.isdisjoint(sys.modules)


def test_auto_rejects_outside_path():
    with pytest.raises(ValueError):
        tool().auto_scope(ROOT, 'all figures', ['../another-project/full.md'], 8192)
