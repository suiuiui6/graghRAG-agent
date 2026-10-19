"""Offline regression evidence for registered pilot resource and data boundaries.

All source data are generated here. Only provider transport is substituted;
registration, hashing, schedules, budgets, bridges and SDK remain real.
"""
from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from research import development_isolation as isolation
from research import new_document_pilot as pilot
from research.development_budget import BudgetLimits, BudgetStopped


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('This suite permits only local MockTransport')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


def write(path, value):
    pilot.dump(path, value)
    return path


def registered(tmp_path):
    runtime = tmp_path / 'runtime'
    source = runtime / 'backend/research/owned.py'
    source.parent.mkdir(parents=True)
    source.write_text('value = 7\n', encoding='utf-8')
    public = runtime / 'public_sources/S.txt'
    public.parent.mkdir()
    public.write_text('合成公开来源\n', encoding='utf-8')
    write(runtime / 'snapshot.json', {'files': {'backend/research/owned.py': pilot.sha(source)}})
    governance = write(tmp_path / 'contract.json', {'scope': 'synthetic-only'})
    reg = {'runtime': str(runtime), 'source_code_files': {'backend/research/owned.py': pilot.sha(source)},
           'sources': {'S': {'file': 'public_sources/S.txt', 'sha256': pilot.sha(public)}},
           'runtime_snapshot_sha256': pilot.sha(runtime / 'snapshot.json'),
           'environment': pilot.common.environment_identity(),
           'governance_sha256': {str(governance): pilot.sha(governance)}}
    profile = tmp_path / 'profile'
    write(profile / 'registration.json', reg)
    write(profile / 'registration.sha256.json', {'registration_sha256': pilot.sha(profile / 'registration.json')})
    return profile, reg, runtime, governance


def test_registration_accepts_intact_owned_inputs_and_frozen_index(tmp_path):
    profile, reg, runtime, _ = registered(tmp_path)
    kg = write(runtime / 'backend/output/kg/S/nodes.json', [{'id': 'n1'}])
    ledger = write(profile / 'index-calls/ledger.json', {'actual_attempts': 0})
    write(profile / 'execution-assets.json', {'kg_files': {'backend/output/kg/S/nodes.json': pilot.sha(kg)},
                                             'index_ledger_sha256': pilot.sha(ledger)})
    write(profile / 'execution-assets.sha256.json', {'sha256': pilot.sha(profile / 'execution-assets.json')})
    assert pilot.verify_registration(profile) == reg


@pytest.mark.parametrize('target,match', [
    ('registration', '登记漂移'), ('source', '已登记文件'), ('canonical', '已登记文件'),
    ('snapshot', '源码快照'), ('governance', '输入或契约'),
    ('environment', '依赖身份'), ('assets', '索引收据'), ('ledger', '索引费用'), ('kg', '已登记文件'),
])
def test_registration_stops_on_each_independent_identity_drift(tmp_path, target, match):
    profile, reg, runtime, governance = registered(tmp_path)
    kg = write(runtime / 'backend/output/kg/S/nodes.json', [])
    ledger = write(profile / 'index-calls/ledger.json', {})
    assets = write(profile / 'execution-assets.json', {'kg_files': {'backend/output/kg/S/nodes.json': pilot.sha(kg)},
                                                      'index_ledger_sha256': pilot.sha(ledger)})
    write(profile / 'execution-assets.sha256.json', {'sha256': pilot.sha(assets)})
    paths = {'registration': profile / 'registration.json', 'source': runtime / 'backend/research/owned.py',
             'canonical': runtime / 'public_sources/S.txt', 'snapshot': runtime / 'snapshot.json',
             'governance': governance, 'assets': assets, 'ledger': ledger, 'kg': kg}
    if target == 'environment':
        reg['environment'] = {'not-the-installed-environment': '0'}
        write(profile / 'registration.json', reg)
        write(profile / 'registration.sha256.json', {'registration_sha256': pilot.sha(profile / 'registration.json')})
    else:
        with paths[target].open('a', encoding='utf-8') as stream:
            stream.write(' ')
    with pytest.raises(ValueError, match=match):
        pilot.verify_registration(profile)


def test_unresolved_worker_writes_zero_cost_result_without_index(tmp_path):
    profile, reg, _, _ = registered(tmp_path)
    unit = {'unit_id': 'Q-r1-A', 'arm': 'A', 'planned_max_attempts': 0}
    reg['schedule'] = [unit]
    write(profile / 'registration.json', reg)
    write(profile / 'registration.sha256.json', {'registration_sha256': pilot.sha(profile / 'registration.json')})
    row = pilot.worker(profile, unit['unit_id'], 0, 0)
    assert row['status'] == 'UNRESOLVED' and row['answer'] is None
    assert row['actual_attempts'] == 0 and row['semantic_scoring'] == 'NOT_ASSESSABLE'
    assert pilot.load(profile / 'out/units/Q-r1-A/result.json') == row
    assert not (profile / 'index-calls').exists()


def test_resolved_worker_requires_frozen_index_before_execution(tmp_path):
    profile, reg, _, _ = registered(tmp_path)
    reg['schedule'] = [{'unit_id': 'Q-r1-P0', 'arm': 'P0', 'planned_max_attempts': 3}]
    write(profile / 'registration.json', reg)
    write(profile / 'registration.sha256.json', {'registration_sha256': pilot.sha(profile / 'registration.json')})
    with pytest.raises(ValueError, match='缺少索引冻结'):
        pilot.worker(profile, 'Q-r1-P0', 1, 3)


def test_dynamic_schedule_keeps_rotations_and_proven_per_arm_bounds():
    work = [{'question_id': f'Q{i}', 'source_id': 'S', 'chunks': [{}, {}],
             'resolution': {'status': status}}
            for i, status in enumerate(('RESOLVED', 'UNRESOLVED'))]
    result = pilot.dynamic_schedule(work, {'S': {'chunks': [{}, {}, {}, {}]}})
    assert len(result) == 18 and len({u['unit_id'] for u in result}) == 18
    assert [u['sequence'] for u in result] == list(range(1, 19))
    for unit in result:
        expected = 3 if unit['arm'] == 'P0' else 5 if unit['arm'] == 'S' else 3 if unit['question_id'] == 'Q0' else 0
        assert unit['planned_max_attempts'] == expected
    assert [u['arm'] for u in result[:6]] == ['P0', 'A', 'S', 'A', 'S', 'P0']


@pytest.mark.parametrize('change', [[], [{'question_id': 'Q', 'source_id': 'elsewhere', 'question': 'q', 'range_condition': 'x'}],
    [{'question_id': '../escape', 'source_id': 'S', 'question': 'q', 'range_condition': 'x'}],
    [{'question_id': 'Q', 'source_id': 'S', 'question': ' ', 'range_condition': 'x'}],
    [{'question_id': 'Q', 'source_id': 'S', 'question': 'q'}]])
def test_question_admission_rejects_invalid_identity_shape_or_text(change):
    with pytest.raises(ValueError):
        pilot.validate_questions(change, 'S')


def test_questions_accept_two_distinct_ids_but_reject_duplicates():
    first = {'question_id': 'Q-1', 'source_id': 'S', 'question': '范围是什么？', 'range_condition': 'all'}
    pilot.validate_questions([first, first | {'question_id': 'Q_2'}], 'S')
    with pytest.raises(ValueError, match='重复'):
        pilot.validate_questions([first, first], 'S')
    assert not pilot.safe_id('汉字') and not pilot.safe_id('a' * 101) and not pilot.safe_id(1)


def index_cap(**updates):
    return {'seconds': 1800, 'single_input_bytes': 24000,
            'actual_prompt_tokens': 16000, 'actual_completion_tokens': 8192} | updates


def index_payload():
    return {'model': 'deepseek-flash', 'max_tokens': 4096, 'thinking': {'type': 'disabled'},
            'messages': [{'role': 'user', 'content': '合成输入'}]}


@pytest.mark.parametrize('tokens,cap', [(8193, {}), (9, {'actual_prompt_tokens': 8}),
                                      (8, {'actual_completion_tokens': 0})])
def test_index_token_overage_preserves_known_cost_before_stopping(tmp_path, tokens, cap):
    Guard = pilot.index_guard_class(index_cap(**cap))
    guard = Guard(tmp_path, 'fixture-not-provider-credential')
    response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"extractions": []}'}}],
                'usage': {'prompt_tokens': tokens, 'completion_tokens': 1, 'total_tokens': tokens + 1}}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))) as client:
        with guard.install(), guard.phase('index', 'S'), pytest.raises(BudgetStopped, match='实际token'):
            client.post('https://api.deepseek.com/chat/completions', json=index_payload())
    saved = pilot.load(tmp_path / 'ledger.json')
    assert saved['closed'] and saved['actual_attempts'] == 1
    assert saved['records'][0]['cost_status'] == 'KNOWN'
    assert saved['records'][0]['usage']['total_tokens'] == tokens + 1


def test_index_single_byte_limit_rejects_before_transport(tmp_path):
    Guard = pilot.index_guard_class(index_cap(single_input_bytes=1))
    guard = Guard(tmp_path, 'fixture-not-provider-credential', BudgetLimits())
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('must not send'))) as client:
        with guard.install(), guard.phase('index'), pytest.raises(BudgetStopped, match='单次字节'):
            client.post('https://api.deepseek.com/chat/completions', json=index_payload())
    assert guard.actual_attempts == 0 and guard.closed


def test_isolation_snapshot_blocks_drift_and_secret_contamination(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'backend').mkdir(parents=True)
    (repo / 'langextract/langextract').mkdir(parents=True)
    (repo / 'backend/a.py').write_text('value=1\n', encoding='utf-8')
    root = tmp_path / 'run'
    isolation.prepare(repo, root)
    assert isolation.verify_snapshot(root)['isolation'] == 'audit-only-windows'
    (root / 'backend/a.py').write_text('value=2\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='源码快照'):
        isolation.verify_snapshot(root)
    (root / 'backend/a.py').write_text('value=1\n', encoding='utf-8')
    # A filename-only contamination sentinel, no credential content.
    (root / 'backend/.env').touch()
    with pytest.raises(RuntimeError, match='不得包含'):
        isolation.verify_snapshot(root)


def test_module_identity_binds_effective_import_to_hash(tmp_path, monkeypatch):
    name = 'pilot_generated_owned_module'
    source = tmp_path / (name + '.py')
    source.write_text('VALUE = 19\n', encoding='utf-8')
    write(tmp_path / 'snapshot.json', {'files': {source.name: isolation.sha(source)}})
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        assert importlib.import_module(name).VALUE == 19
        identity = isolation.module_identity(tmp_path, (name,))
        assert identity[name]['sha256'] == isolation.sha(source)
        source.write_text('VALUE = 20\n', encoding='utf-8')
        with pytest.raises(RuntimeError, match='未绑定隔离源码'):
            isolation.module_identity(tmp_path, (name,))
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize('interval', [None, (True, 2), (-1, 2), (2, 2), (0, 99), (0, 1, 2)])
def test_grounding_invalid_coordinates_never_claim_source_evidence(interval):
    result = isolation.grounding_evidence('abc', SimpleNamespace(char_interval=interval,
                extraction_text='a', grounding_status='grounded'))
    assert result['source_interval_valid'] is False
    assert result['exact_text_match'] is False
    assert result['source_slice'] is None and result['source_slice_sha256'] is None


def test_source_units_and_pdf_bridge_preserve_lf_unicode_and_source_hashes(tmp_path):
    canonical = tmp_path / 'source.txt'
    text = '1. Scope\n合成证据\n'
    canonical.write_bytes(text.encode('utf-8'))
    raw = tmp_path / 'source.pdf'; raw.write_bytes(b'%PDF-1.4 synthetic identity only')
    mapping = write(tmp_path / 'mapping.json', {'pages': [{'start': 0, 'end': len(text), 'text': text,
                'pdf_page_zero_based': 0, 'pdf_page_one_based': 1}]})
    xml = tmp_path / 'source.xml'
    xml.write_text('<pdf2xml><page number="1"><fontspec id="0" family="Synthetic-Bold"/>'
                   '<text font="0">1. Scope</text></page></pdf2xml>', encoding='utf-8')
    record = {'source_id': 'S', 'raw_file': raw.name, 'canonical_file': canonical.name,
              'section_or_page_map': mapping.name, 'source_sha256': isolation.sha(raw),
              'canonical_sha256': isolation.sha(canonical)}
    manifest = write(tmp_path / 'sources.json', [record])
    units = isolation._source_units(manifest)
    assert len(units) == 1 and units[0][1] == text
    documents, position, offsets, bridge = isolation._bridge_source(*units[0], xml)
    # The bridge deliberately strips section-edge whitespace, retaining the
    # canonical text and exact offset map for grounding.
    assert [d.text for d in documents] == ['1. Scope\n合成证据']
    assert offsets == {'S-section-000': 0}
    assert position.lookup_range(0, len(text)).text == text
    assert bridge['structure']['nodes'][0]['title'] == '1. Scope'
    assert bridge['position_map']['segments'][0]['text'] == text
    canonical.write_text('drift', encoding='utf-8')
    with pytest.raises(RuntimeError, match='公开来源身份'):
        isolation._source_units(manifest)


def test_bounded_sdk_factory_restores_global_entrypoints_after_exception():
    import langextract as lx
    import langextract.factory as factory
    before = factory.create_model, lx.extract
    with pytest.raises(RuntimeError, match='sentinel'):
        with isolation.bounded_langextract():
            assert factory.create_model is not before[0] and lx.extract is not before[1]
            raise RuntimeError('sentinel')
    assert (factory.create_model, lx.extract) == before


def test_copy_runtime_binds_current_runner_and_preserves_frozen_source(tmp_path):
    frozen = tmp_path / 'frozen'
    original = frozen / 'backend/research/owned.py'
    original.parent.mkdir(parents=True)
    original.write_text('VALUE = 101\n', encoding='utf-8')
    write(frozen / 'snapshot.json', {'files': {'backend/research/owned.py': pilot.sha(original)}})
    before = pilot.sha(original)
    runtime = tmp_path / 'runtime'
    copied = pilot.copy_runtime(frozen, runtime)
    assert pilot.sha(original) == before
    assert copied['backend/research/owned.py'] == before
    assert copied['backend/research/new_document_pilot.py'] == pilot.sha(pilot.__file__)
    assert copied['backend/research/common_three_arm.py'] == pilot.sha(pilot.common.__file__)
    assert pilot.load(runtime / 'snapshot.json')['files'] == copied
    assert (runtime / 'backend/output/kg').is_dir() and (runtime / 'home/AppData/Local').is_dir()
    with pytest.raises(FileExistsError):
        pilot.copy_runtime(frozen, runtime)
    original.write_text('VALUE = 102\n', encoding='utf-8')
    with pytest.raises(ValueError, match='已登记文件'):
        pilot.copy_runtime(frozen, tmp_path / 'must-not-exist')
    assert not (tmp_path / 'must-not-exist').exists()


@pytest.mark.parametrize('sources', [[], [{'source_id': 'S'}] * 2, [{'source_id': f'S{i}'} for i in range(4)]])
def test_prepare_refuses_bad_source_admission_before_opening_runtime(tmp_path, sources):
    batch = write(tmp_path / 'batch.json', {'sources': sources})
    root = tmp_path / 'not-created'
    with pytest.raises(ValueError, match='1至3份独立来源'):
        pilot.prepare(batch, tmp_path / 'absent-frozen', tmp_path / 'absent-prompt', root)
    assert not root.exists()


@pytest.mark.parametrize('fault,match', [('unsafe_id', '来源标识'), ('manifest', '单源manifest'),
    ('suffix', '仅PDF'), ('hash', '来源hash'), ('length', '来源超预登记长度'), ('questions', '问题来源或文本')])
def test_prepare_validates_public_data_before_starting_any_worker(tmp_path, fault, match):
    # A genuinely hash-registered prompt profile, not a verify_registration stub.
    prompt = tmp_path / 'prompt'
    runtime = prompt / 'runtime'
    write(runtime / 'snapshot.json', {'files': {}})
    reg = {'runtime': str(runtime), 'source_code_files': {}, 'kg_files': {}, 'sources': {},
           'runtime_snapshot_sha256': pilot.sha(runtime / 'snapshot.json'),
           'environment': pilot.common.environment_identity(), 'governance_sha256': {},
           'kg_provenance_sha256': {}}
    write(prompt / 'registration.json', reg)
    write(prompt / 'registration.sha256.json', {'registration_sha256': pilot.sha(prompt / 'registration.json')})
    assert pilot.common.verify_registration(prompt) == reg
    raw = tmp_path / ('source.html' if fault == 'suffix' else 'source.pdf')
    raw.write_bytes(b'%PDF-1.4 synthetic source admission')
    canonical = tmp_path / 'canonical.txt'
    canonical.write_text('' if fault == 'length' else 'Synthetic source content.', encoding='utf-8')
    mapping = write(tmp_path / 'mapping.json', [])
    record = {'source_id': 'S', 'raw_file': raw.name, 'canonical_file': canonical.name,
              'section_or_page_map': mapping.name, 'source_sha256': 'wrong' if fault == 'hash' else pilot.sha(raw),
              'canonical_sha256': pilot.sha(canonical)}
    manifest = write(tmp_path / 'sources.json', [] if fault == 'manifest' else [record])
    questions = write(tmp_path / 'questions.json', [{'question_id': 'Q', 'source_id': 'S',
                      'question': ' ' if fault == 'questions' else 'What is the scope?', 'range_condition': 'all'}])
    xml = tmp_path / 'source.xml'; xml.write_text('<pdf2xml/>', encoding='utf-8')
    batch = write(tmp_path / 'batch.json', {'sources': [{'source_id': '../escape' if fault == 'unsafe_id' else 'S',
                  'manifest_file': manifest.name, 'xml_file': xml.name, 'questions_file': questions.name}]})
    root = tmp_path / 'run'
    with pytest.raises(ValueError, match=match):
        pilot.prepare(batch, tmp_path / 'absent-frozen', prompt, root)
    assert not (root / 'S/runtime').exists()
    assert not (root / 'batch-registration.json').exists()


def test_real_sdk_index_transport_retains_usage_and_hardens_model(tmp_path):
    import langextract.factory as factory
    from research.development_budget import openai_transport_module
    sdk_http = openai_transport_module()
    seen = []
    def transport(request):
        seen.append(json.loads(request.content))
        return sdk_http.Response(200, request=request, json={
            'id': 'synthetic-only', 'object': 'chat.completion', 'created': 0, 'model': 'deepseek-flash',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"extractions": []}'}}],
            'usage': {'prompt_tokens': 8, 'completion_tokens': 1, 'total_tokens': 9}})
    Guard = pilot.index_guard_class(index_cap())
    guard = Guard(tmp_path, 'fixture-not-provider-credential')
    with guard.install(), guard.phase('index', 'S'), isolation.bounded_langextract(
            http_client_factory=lambda: sdk_http.Client(transport=sdk_http.MockTransport(transport), trust_env=False)) as details:
        model = factory.create_model(factory.ModelConfig(model_id='deepseek-flash', provider='openai',
                    provider_kwargs={'api_key': 'fixture-not-provider-credential', 'base_url': 'https://api.deepseek.com'}))
        result = model._process_single_prompt('Synthetic text without real source data', model._extra_kwargs)
    assert result.output == '{"extractions": []}'
    assert len(seen) == 1 and seen[0]['max_tokens'] == 4096
    assert seen[0]['thinking'] == {'type': 'disabled'}
    assert details[0]['sdk_max_retries'] == 0 and details[0]['provider_workers'] == 1
    assert guard.actual_attempts == 1 and not guard.closed
    assert pilot.load(tmp_path / 'ledger.json')['records'][0]['usage']['total_tokens'] == 9


def test_full_preflight_runs_real_copied_worker_bridge_and_sdk_without_provider(tmp_path):
    """Fresh-process activation avoids contaminating other collected tests."""
    repository = Path(__file__).resolve().parents[2]
    runtime = tmp_path / 'runtime'
    isolation.prepare(repository, runtime)
    text = '1. Scope\nSynthetic public fixture content for an offline extraction preflight.\n'
    canonical = tmp_path / 'source.txt'; canonical.write_bytes(text.encode())
    raw = tmp_path / 'source.pdf'; raw.write_bytes(b'%PDF-1.4 synthetic fixture only')
    mapping = write(tmp_path / 'mapping.json', {'pages': [{'start': 0, 'end': len(text), 'text': text,
        'pdf_page_zero_based': 0, 'pdf_page_one_based': 1}]})
    xml = tmp_path / 'source.xml'
    xml.write_text('<pdf2xml><page number="1"><fontspec id="0" family="Synthetic-Bold"/>'
                   '<text font="0">1. Scope</text></page></pdf2xml>', encoding='utf-8')
    manifest = write(tmp_path / 'sources.json', [{'source_id': 'S', 'raw_file': raw.name,
        'canonical_file': canonical.name, 'section_or_page_map': mapping.name,
        'source_sha256': isolation.sha(raw), 'canonical_sha256': isolation.sha(canonical)}])
    script = '''
import json, os, socket, sys
def deny(*args, **kwargs):
    raise AssertionError('network forbidden before native imports')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = deny
from research.development_isolation import activate, preflight_sources
root = activate(sys.argv[1])
result = preflight_sources(root, sys.argv[2], sys.argv[3])
assert socket.create_connection is deny
assert 'LANGEXTRACT_API_KEY' not in os.environ
assert result['mode'] == 'SIMULATED_NO_PROVIDER_USAGE'
assert result['planned_requests'] >= 1
try:
    preflight_sources(root, sys.argv[2], sys.argv[3])
except FileExistsError:
    pass
else:
    raise AssertionError('must refuse preflight overwrite')
print('OFFLINE_PREFLIGHT_OK')
'''
    env = os.environ.copy()
    env.pop('LANGEXTRACT_API_KEY', None)
    env.update(PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTHONPATH=str(repository / 'langextract') + os.pathsep + str(repository / 'backend'))
    completed = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', script,
                               str(runtime), str(manifest), str(xml)],
                              env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert 'OFFLINE_PREFLIGHT_OK' in completed.stdout
    receipt = pilot.load(runtime / 'artifacts/preflight.json')
    assert receipt['planned_input_bytes'] == sum(item['input_bytes'] for item in receipt['requests'])
    assert receipt['sources'][0]['bridge']['documents'][0]['text'] == text.strip()
    assert all(Path(m['path']).is_relative_to(runtime) for m in receipt['modules'].values())
    assert not (runtime / 'backend/output/docs_store.json').exists()
    assert not list((runtime / 'backend/output/kg').rglob('*.json'))
