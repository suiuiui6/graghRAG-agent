import argparse
import builtins
import json
import pathlib
import runpy
import sys
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend_validation as bv
import conversation_validation as cv
import release_gate as gate
import run_inference as runner


def test_ground_truth_builder_redirects_all_io(tmp_path, monkeypatch):
    """Execute exact builder source with import-level path injection, never original KG/Gold."""
    source = pathlib.Path(__file__).resolve().parents[1] / 'build_ground_truth.py'
    fixture = tmp_path / 'kg'
    fixture.mkdir()
    nodes = [dict(node_id=f'n{i:04d}', grounding_status='grounded' if i % 2 else 'unknown',
                  entity_type='TEST_ONLY', label='TEST_ONLY') for i in range(500)]
    (fixture / 'nodes.json').write_text(json.dumps({'nodes': nodes}), encoding='utf-8')
    (fixture / 'edges.json').write_text(json.dumps({'edges': []}), encoding='utf-8')
    target = tmp_path / 'synthetic-ground-truth.json'
    real_import = builtins.__import__
    def redirect_path(value):
        if value == 'D:/graghRAG-agent/backend/output/kg/doc_ingest_232e1611':
            return fixture
        if value == 'D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/ground_truth.json':
            return target
        raise AssertionError(f'Unexpected builder path: {value}')
    def isolated_import(name, *args, **kwargs):
        if name == 'pathlib':
            return SimpleNamespace(Path=redirect_path)
        return real_import(name, *args, **kwargs)
    with monkeypatch.context() as scope:
        scope.setattr(builtins, '__import__', isolated_import)
        namespace = runpy.run_path(str(source))
    data = json.loads(target.read_text(encoding='utf-8'))
    assert len(data['questions']) == 50
    assert data['_meta']['kg_nodes_total'] == 500
    assert data['_meta']['category_counts']['T5'] == 10
    assert all(n in namespace['NODES'] for q in data['questions'] for n in q['expected_node_ids'])
    with pytest.raises(AssertionError, match='not in KG'):
        namespace['add']('invalid', 'T1', 'test', ['nonexistent'])


@pytest.mark.parametrize('module', [bv, cv])
@pytest.mark.parametrize('exit_code', [0, 2])
def test_validation_cli_persists_actual_boundary_result(module, exit_code, tmp_path, monkeypatch):
    calls = []
    def process(args, *, cwd):
        calls.append((args, cwd))
        return exit_code, '2 passed in 0.1s' if exit_code == 0 else '1 failed in 0.1s'
    monkeypatch.setattr(module, '_run_pytest_in_process', process)
    monkeypatch.setattr(module, 'OUT_PATH', tmp_path / 'summary.json')
    if exit_code:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == exit_code
    else:
        module.main()
    result = json.loads(module.OUT_PATH.read_text(encoding='utf-8'))
    assert result['exit_code'] == exit_code
    assert result['summary'].startswith('2 passed' if exit_code == 0 else '1 failed')
    assert calls[0][1] == module.BACKEND_DIR
    assert calls[0][0][0].startswith('tests')


def test_validation_absent_environment_and_warning_details(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, 'BACKEND_DIR', tmp_path)
    with pytest.raises(FileNotFoundError, match='Backend venv'):
        bv._backend_python_executable()
    assert bv._normalize_warning_detail(' custom warning ') == 'custom warning'
    assert bv.parse_pytest_output('warnings summary\nUserWarning: incomplete')['warnings'] == []


@pytest.mark.parametrize('supplemental', [False, True])
def test_release_cli_real_inputs_and_optional_evidence(supplemental, tmp_path, monkeypatch):
    for name in ('A1_PATH', 'A2_PATH', 'A5_PATH', 'BACKEND_VALIDATION_PATH', 'CONVERSATION_VALIDATION_PATH',
                 'CONVERSATION_REWRITE_METRICS_PATH', 'RAW_RUNS_PATH', 'RUN_LOG_PATH', 'OUT_JSON', 'OUT_MD'):
        monkeypatch.setattr(gate, name, tmp_path / name)
    gate.A1_PATH.write_text(json.dumps({'surfaces': {'final_context': {'global': {'recall_macro': .8}, 'surface_data_coverage': 39}}}), encoding='utf-8')
    gate.A2_PATH.write_text(json.dumps({'global': {'keyword_coverage_macro': .9, 'cited_in_retrieved_rate_macro': 1}, 'by_category': {'T5': {'refusal_for_t5_macro': .5 if supplemental else 1}}}), encoding='utf-8')
    gate.A5_PATH.write_text(json.dumps({'latency_ms': {'global': {'p95': 1000, 'p99': 2000}}}), encoding='utf-8')
    if supplemental:
        for path in (gate.BACKEND_VALIDATION_PATH, gate.CONVERSATION_VALIDATION_PATH):
            path.write_text(json.dumps({'exit_code': 0, 'summary': '1 passed'}), encoding='utf-8')
        gate.CONVERSATION_REWRITE_METRICS_PATH.write_text(json.dumps({'global': {'followup_questions': 1}}), encoding='utf-8')
        gate.RAW_RUNS_PATH.write_text('TEST_ONLY', encoding='utf-8')
    gate.main()
    result = json.loads(gate.OUT_JSON.read_text(encoding='utf-8'))
    assert result['_meta']['raw_runs_sha256'] is not None if supplemental else result['_meta']['raw_runs_sha256'] is None
    assert len(result['_meta']['non_gated_notes']) == (2 if supplemental else 0)
    assert ('Release' in gate.OUT_MD.read_text(encoding='utf-8'))


def test_runner_cli_resume_setup_success_and_failure(tmp_path, monkeypatch):
    gt = tmp_path / 'gt.json'
    out, log = tmp_path / 'runs.jsonl', tmp_path / 'run.log'
    gt.write_text(json.dumps({'questions': [
        dict(qid='existing', category='T1', question='existing'),
        dict(qid='ok', category='T1', question='ok', session_id='s', conversation_setup=[None, {}, {'question': 'setup'}]),
        dict(qid='fail', category='T5', question='fail')]}), encoding='utf-8')
    out.write_text('\ninvalid-json\n{}\n' + json.dumps({'qid': 'existing'}) + '\n', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['run_inference', '--append', '--skip-existing', '--gt-path', str(gt), '--out-path', str(out), '--log-path', str(log)])
    monkeypatch.setattr(runner, '_require_api_key', lambda: None)
    requests = []
    app = FastAPI()
    @app.post('/api/v1/rag/query')
    def answer(payload: dict):
        requests.append(payload)
        if payload['query'] == 'fail':
            raise RuntimeError('TEST_ONLY failure')
        return {'answer': 'result n0001', 'sources': [{'label': 'node n0001', 'text': 'x'*300}], 'metadata': {'duration_ms': 42}}
    monkeypatch.setattr(runner, '_load_test_client', lambda: TestClient(app))
    runner.main()
    rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()[4:]]
    assert [r['qid'] for r in rows] == ['ok', 'fail']
    assert rows[0]['final_answer'] == 'result n0001'
    assert rows[0]['latency_ms'] == 42
    assert rows[0]['source_text_snippets'] == ['x'*240+'...']
    assert rows[1]['error'] == 'RuntimeError: TEST_ONLY failure'
    assert [r['query'] for r in requests] == ['setup', 'ok', 'fail']
    assert all(r['options']['include_sources'] for r in requests)
    assert 'ERROR' in log.read_text(encoding='utf-8')


def test_runner_options_environment_and_key_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['run_inference'])
    for name in ('RAG_EVAL_APPEND', 'RAG_EVAL_SKIP_EXISTING', 'RAG_EVAL_OUT_PATH', 'RAG_EVAL_LOG_PATH', 'RAG_EVAL_GT_PATH', 'RAG_EVAL_LIMIT'):
        monkeypatch.delenv(name, raising=False)
    assert not runner.parse_args().append
    monkeypatch.setenv('RAG_EVAL_APPEND', 'yes')
    monkeypatch.setenv('RAG_EVAL_LIMIT', '2')
    assert runner.parse_args().append and runner.parse_args().limit == 2
    assert runner.resolve_ground_truth_path(SimpleNamespace(gt_path=None)) == runner.GT_PATH
    assert runner._load_existing_qids(tmp_path/'absent') == set()
    assert runner._build_request_payload('question')['query'] == 'question'
    assert runner._truncate_source_text(' short ') == 'short'
    assert runner.select_questions([{'qid': 'a'}, {'qid': 'b'}], None, 1, None) == [{'qid': 'b'}]
    calls = []
    monkeypatch.setattr(runner, 'load_dotenv', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('LANGEXTRACT_API_KEY', raising=False)
    with pytest.raises(SystemExit, match='Missing'):
        runner._require_api_key()
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'TEST_ONLY')
    runner._require_api_key()
    assert calls[0][1] == {'override': True}
    monkeypatch.setattr(runner, 'BACKEND_DIR', tmp_path)
    runner._ensure_backend_import_path()
    assert str(tmp_path) in sys.path
    monkeypatch.setattr(sys, 'path', [p for p in sys.path if p != str(tmp_path)])


def test_runner_client_loader_uses_isolated_app(monkeypatch):
    app = FastAPI()
    monkeypatch.setitem(sys.modules, 'server', SimpleNamespace(app=app))
    monkeypatch.setattr(runner, '_ensure_backend_import_path', lambda: None)
    with runner._load_test_client() as client:
        assert client.get('/missing').status_code == 404


def test_runner_no_resume_and_response_wall_clock_fallback(tmp_path, monkeypatch):
    gt = tmp_path / 'gt.json'
    gt.write_text(json.dumps({'questions': [{'qid': 'A', 'question': 'TEST_ONLY', 'category': 'T1'}]}), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['run', '--gt-path', str(gt), '--out-path', str(tmp_path/'runs'), '--log-path', str(tmp_path/'log')])
    monkeypatch.setattr(runner, '_require_api_key', lambda: None)
    app = FastAPI()
    @app.post('/api/v1/rag/query')
    def answer(payload: dict):
        return {'answer': 'TEST_ONLY'}
    monkeypatch.setattr(runner, '_load_test_client', lambda: TestClient(app))
    monkeypatch.setattr(runner, 'time', SimpleNamespace(time=iter([10.0, 10.123]).__next__))
    runner.main()
    result = json.loads((tmp_path/'runs').read_text(encoding='utf-8'))
    assert result['error'] is None
    assert result['latency_ms'] == 122
    assert result['http_status'] == 200
