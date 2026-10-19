"""Real local CLI, admission and isolation boundaries; no provider access."""
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import tempfile

import pytest
import requests

from research import development_isolation as isolation
from research import development_profile_cli as profile
from research import isolation_snapshot as snapshot
from research import new_document_pilot as pilot


@pytest.fixture(autouse=True)
def deny_provider(monkeypatch):
    def denied(*a, **kw):
        raise AssertionError('Only synthetic local transport is allowed')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


@contextmanager
def activation_state(monkeypatch):
    """Supply the documented fresh-import precondition and restore all state."""
    names = ('worker', 'routes', 'schema', 'langextract', 'generator', 'retrieval')
    variables = ('TMP', 'TEMP', 'TMPDIR', 'HF_HOME', 'TRANSFORMERS_CACHE',
        'SENTENCE_TRANSFORMERS_HOME', 'XDG_CACHE_HOME', 'HF_HUB_OFFLINE',
        'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE', 'LANGEXTRACT_MODEL_ID', 'LANGEXTRACT_BASE_URL')
    with monkeypatch.context() as m:
        m.setattr(sys, 'path', sys.path.copy())
        m.chdir(Path.cwd())
        m.setattr(tempfile, 'tempdir', tempfile.tempdir)
        for name in names:
            m.delitem(sys.modules, name, raising=False)
        for name in variables:
            m.setenv(name, os.environ.get(name, 'test-restore-placeholder'))
        yield


def empty_runtime(tmp_path):
    root = tmp_path / 'runtime'
    dump(root / 'snapshot.json', {'files': {}})
    for relative in ('backend', 'temp', 'cache'):
        (root / relative).mkdir(exist_ok=True)
    return root


def test_activate_hardens_paths_environment_and_restores_test_process(tmp_path, monkeypatch):
    root = empty_runtime(tmp_path)
    before = Path.cwd(), sys.path.copy(), dict(os.environ), tempfile.tempdir
    with activation_state(monkeypatch):
        assert isolation.activate(root) == root.resolve()
        assert Path.cwd() == root / 'backend'
        assert sys.path[:2] == [str(root / 'backend'), str(root / 'langextract')]
        assert tempfile.tempdir == str(root / 'temp')
        for key in ('TMP', 'TEMP', 'TMPDIR'):
            assert os.environ[key] == str(root / 'temp')
        for key in ('HF_HOME', 'TRANSFORMERS_CACHE', 'SENTENCE_TRANSFORMERS_HOME', 'XDG_CACHE_HOME'):
            assert os.environ[key] == str(root / 'cache')
        assert os.environ['HF_HUB_OFFLINE'] == os.environ['TRANSFORMERS_OFFLINE'] == '1'
    assert (Path.cwd(), sys.path, dict(os.environ), tempfile.tempdir) == before


def test_activate_rejects_native_import_before_mutating_process(tmp_path):
    root = empty_runtime(tmp_path)
    importlib.import_module('schema')
    before = Path.cwd(), sys.path.copy(), dict(os.environ), tempfile.tempdir
    with pytest.raises(RuntimeError, match='原生模块导入前'):
        isolation.activate(root)
    assert (Path.cwd(), sys.path, dict(os.environ), tempfile.tempdir) == before


@pytest.mark.parametrize('mode,fields', [
    ('prepare', ['--batch', 'missing-batch.json', '--frozen', 'missing-frozen', '--prompt-profile', 'missing-prompt']),
    ('preflight', []), ('index', []), ('worker', ['--unit-id', 'Q', '--deadline', '1', '--remaining', '1']),
    ('run', ['--env-file', 'not-opened-by-admission'])])
def test_pilot_main_dispatches_real_missing_input_rejections(tmp_path, monkeypatch, mode, fields):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['pilot', mode, '--root', str(tmp_path / 'missing-root'), *fields])
    with pytest.raises(FileNotFoundError):
        pilot.main()
    assert not (tmp_path / 'missing-root').exists()


@pytest.mark.parametrize('module', [pilot, isolation, profile])
def test_real_module_entrypoint_help_never_opens_inputs_or_starts_provider(tmp_path, monkeypatch, capsys, module):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    monkeypatch.setattr(sys, 'argv', [module.__file__, '--help'])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(module.__file__, run_name='__main__')
    assert exited.value.code == 0
    assert 'usage:' in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_isolation_main_prepare_copies_only_synthetic_sources(tmp_path, monkeypatch, capsys):
    repo = tmp_path / 'project'
    (repo / 'backend').mkdir(parents=True)
    (repo / 'backend/owned.py').write_text('VALUE = 1\n', encoding='utf-8')
    (repo / 'langextract/langextract').mkdir(parents=True)
    root = tmp_path / 'runtime'
    monkeypatch.setattr(sys, 'argv', ['isolation', 'prepare', '--repo-root', str(repo), '--run-root', str(root)])
    isolation.main()
    assert json.loads(capsys.readouterr().out) == {'status': 'PREPARED'}
    assert (root / 'backend/owned.py').read_text() == 'VALUE = 1\n'
    assert isolation.verify_snapshot(root)['files']


@pytest.mark.parametrize('mode', ['preflight', 'index', 'query'])
def test_isolation_main_rejects_nonfresh_activation(tmp_path, monkeypatch, mode):
    root = empty_runtime(tmp_path)
    importlib.import_module('schema')
    monkeypatch.setattr(sys, 'argv', ['isolation', mode, '--run-root', str(root)])
    with pytest.raises(RuntimeError, match='原生模块导入前'):
        isolation.main()


def pilot_profile(tmp_path, *, verified=True):
    p = tmp_path / 'profile'
    runtime = p / 'runtime'
    dump(runtime / 'snapshot.json', {'files': {}})
    reg = {'runtime': str(runtime), 'source_code_files': {}, 'sources': {},
           'runtime_snapshot_sha256': pilot.sha(runtime / 'snapshot.json'),
           'environment': pilot.common.environment_identity(), 'governance_sha256': {},
           'data_freeze_verified': verified}
    dump(p / 'registration.json', reg)
    dump(p / 'registration.sha256.json', {'registration_sha256': pilot.sha(p / 'registration.json')})
    source = {'profile': str(p), 'registration_sha256': pilot.sha(p / 'registration.json')}
    batch = dump(tmp_path / 'batch-registration.json', {'sources': [source], 'total_units': 0})
    dump(tmp_path / 'batch-registration.sha256.json', {'sha256': pilot.sha(batch)})
    return p, batch


@pytest.mark.parametrize('fault,match', [('batch', '批次登记'), ('replay', '禁止续跑'),
    ('freeze', '独立数据冻结'), ('source_receipt', '源登记'), ('missing_authorization', '缺少授权')])
def test_pilot_run_admission_stops_before_any_paid_or_index_worker(tmp_path, fault, match):
    p, batch = pilot_profile(tmp_path, verified=fault != 'freeze')
    if fault == 'batch':
        batch.write_text(batch.read_text() + ' ', encoding='utf-8')
    elif fault == 'replay':
        dump(tmp_path / 'run-started.json', {'epoch': 0})
    elif fault == 'source_receipt':
        data = pilot.load(batch)
        data['sources'][0]['registration_sha256'] = 'wrong'
        dump(batch, data)
        dump(tmp_path / 'batch-registration.sha256.json', {'sha256': pilot.sha(batch)})
    with pytest.raises(ValueError, match=match):
        pilot.run(tmp_path, tmp_path / 'absent-synthetic-auth-fixture')
    assert not (p / 'index-process.json').exists()
    if fault != 'replay':
        assert not (tmp_path / 'run-started.json').exists()


def data_fixture(tmp_path):
    data = tmp_path / 'data'; data.mkdir()
    texts = ['1. Scope', 'Synthetic content with enough text for a real map chunk.', '2. Other', 'Unrelated synthetic content.']
    canonical = '\n'.join(texts) + '\n'
    raw = data / 'source.html'
    raw.write_text('<html><body><h1>1. Scope</h1><p>' + texts[1] + '</p><h1>2. Other</h1><p>' + texts[3] + '</p></body></html>', encoding='utf-8')
    source = data / 'source.txt'; source.write_bytes(canonical.encode())
    blocks = []
    start = 0
    for i, text in enumerate(texts):
        tag = 'h1' if i % 2 == 0 else 'p'
        blocks.append({'start': start, 'end': start + len(text), 'text': text, 'tag': tag,
                       'xpath': f'/html[1]/body[1]/{tag}[{i // 2 + 1}]'})
        start += len(text) + 1
    mapping = dump(data / 'map.json', {'blocks': blocks})
    record = {'source_id': 'S', 'canonical_file': source.name, 'raw_file': raw.name,
              'section_or_page_map': mapping.name, 'canonical_sha256': profile.sha(source), 'source_sha256': profile.sha(raw)}
    dump(data / 'sources.json', [record])
    questions = [{'question_id': f'Q{i}', 'source_id': 'S', 'question': 'section 1' if i == 0 else 'unclear scope',
                  'range_condition': 'synthetic-only'} for i in range(6)]
    dump(data / 'questions.input.json', questions)
    xml = data / 'unused.xml'; xml.write_text('<pdf2xml/>', encoding='utf-8')
    previous = dump(data / 'previous.json', {'units': [{'messages': [{'content': 'Synthetic system'}]}],
                     'map_instruction': 'Summarize exact source', 'reduce_instruction': 'Use provided maps'})
    return data, xml, previous, canonical


def test_profile_prepare_without_progress_uses_real_source_and_resolver(tmp_path):
    data, xml, previous, text = data_fixture(tmp_path)
    artifacts = tmp_path / 'artifacts'
    profile.prepare_inputs(data, xml, artifacts, previous)
    prepared = profile.load(artifacts / 'inputs.json')
    assert prepared['gold_loaded'] is False and prepared['A_planned_calls'] == 2
    assert prepared['work'][0]['resolution']['status'] == 'RESOLVED'
    span = prepared['work'][0]['chunks'][0]
    assert text[span['start']:span['end']] == '1. Scope\nSynthetic content with enough text for a real map chunk.\n'
    assert [w['planned_calls'] for w in prepared['work'][1:]] == [0] * 5


@pytest.mark.parametrize('via_main', [False, True])
def test_profile_run_a_real_budget_maps_reduces_and_abstains_without_network(tmp_path, monkeypatch, capsys, via_main):
    data, xml, previous, text = data_fixture(tmp_path)
    artifacts = tmp_path / 'artifacts'
    profile.prepare_inputs(data, xml, artifacts, previous)
    root = empty_runtime(tmp_path)
    wire = []
    def send(session, request, **kwargs):
        wire.append(json.loads(request.body))
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': 'Synthetic answer'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}}).encode()
        result.request = request
        return result
    monkeypatch.setattr(requests.Session, 'send', send)
    monkeypatch.setenv('LANGEXTRACT_API_KEY', 'synthetic-transport-fixture')
    ledger = tmp_path / 'ledger'
    with activation_state(monkeypatch):
        if via_main:
            monkeypatch.setattr(sys, 'argv', ['profile', 'run-a', '--run-root', str(root), '--artifacts', str(artifacts), '--ledger', str(ledger)])
            profile.main()
        else:
            profile.run_a(root, artifacts, ledger)
    rows = profile.load(artifacts / 'A-result.json')['work']
    assert len(rows) == 6 and rows[0]['status'] == 'COMPLETED'
    assert rows[0]['answer'] == 'Synthetic answer'
    assert all(r['calls'] == 0 and r['status'] == 'UNRESOLVED' for r in rows[1:])
    assert len(wire) == 2
    assert text[:text.index('2. Other')] in wire[0]['messages'][1]['content']
    assert 'Synthetic answer' in wire[1]['messages'][1]['content']
    assert profile.load(ledger / 'ledger.json')['actual_attempts'] == 2
    if via_main:
        assert json.loads(capsys.readouterr().out)['actual_attempts'] == 2


def test_profile_main_prepare_uses_real_inputs_and_json_progress(tmp_path, monkeypatch, capsys):
    data, xml, previous, _ = data_fixture(tmp_path)
    artifacts = tmp_path / 'artifacts'
    monkeypatch.setattr(sys, 'argv', ['profile', 'prepare-inputs', '--data-dir', str(data), '--xml', str(xml),
        '--previous-manifest', str(previous), '--artifacts', str(artifacts)])
    profile.main()
    event = json.loads(capsys.readouterr().out)
    assert event['status'] == 'PREPARED_NOT_EXECUTED' and event['A_planned_calls'] == 2


def put(path, content=b'synthetic'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def physical_fixture(tmp_path, include_site=True):
    root = tmp_path / 'project'
    put(root / 'backend/owned.py', b'VALUE=1\n')
    put(root / 'backend/config/domain_dict.yaml', b'terms: []')
    if include_site:
        put(root / 'backend/.venv/Lib/site-packages/tiny/__init__.py', b'VALUE=1\n')
    base = tmp_path / 'base'
    executable = put(base / 'python.exe', b'synthetic executable never launched')
    put(base / 'python312.dll')
    put(base / 'Lib/pathlib.py', b'VALUE=1\n')
    return root, executable


def test_fingerprint_refuses_directory_as_source(tmp_path):
    with pytest.raises(ValueError, match='regular file'):
        snapshot._fingerprint(tmp_path)


def test_snapshot_requires_local_site_packages_before_creating_run(tmp_path):
    root, executable = physical_fixture(tmp_path, include_site=False)
    with pytest.raises(ValueError, match='site-packages is missing'):
        snapshot.prepare_snapshot(root, 'missing-site', executable)
    assert not (root / 'backend/output/research-isolation/missing-site').exists()


def test_snapshot_refuses_nonempty_rollback_journal(tmp_path):
    root, executable = physical_fixture(tmp_path)
    put(root / 'backend/output/runtime.db-journal', b'active transaction')
    with pytest.raises(ValueError, match='rollback journal'):
        snapshot.prepare_snapshot(root, 'journal', executable)
    assert not (root / 'backend/output/research-isolation/journal').exists()


def test_snapshot_relative_pth_stays_inert_and_directory_named_python_is_not_code(tmp_path):
    root, executable = physical_fixture(tmp_path)
    site = root / 'backend/.venv/Lib/site-packages'
    put(site / 'local.pth', b'# inert configuration\ntiny\n')
    (root / 'backend/directory.py').mkdir()
    manifest = snapshot.prepare_snapshot(root, 'relative-pth', executable)
    run = Path(manifest['run_root'])
    assert manifest['status'] == 'verified'
    assert (run / 'python/Lib/site-packages/local.pth').read_bytes() == b'# inert configuration\ntiny\n'
    assert not (run / 'backend/directory.py').exists()
