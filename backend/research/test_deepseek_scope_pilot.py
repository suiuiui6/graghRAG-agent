"""Software fixtures only; these are not scientific evaluation results."""
import importlib.util
import json
from pathlib import Path
import sys
import shutil
import uuid

import httpx
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture
def tmp_path():
    # pytest's mode=0o700 temporary root triggers restricted Windows ACLs.
    # Ordinary inherited workspace permissions avoid that unrelated failure.
    # Generated Python fixtures belong to the existing test-only tree. Keeping
    # them beside production modules makes coverage trace deleted source files.
    fixture_parent = HERE.parent / 'tests' / '_sandbox_tmp' / 'research-pilot'
    fixture_parent.mkdir(parents=True, exist_ok=True)
    root = (fixture_parent / ('test-fixture-' + uuid.uuid4().hex)).resolve()
    assert root.parent == fixture_parent.resolve()
    root.mkdir()
    try:
        yield root
    finally:
        assert root.parent == fixture_parent.resolve() and root.name.startswith('test-fixture-')
        shutil.rmtree(root)


def adapter():
    path = HERE / 'deepseek_scope_pilot.py'
    assert path.exists(), 'Bounded adapter has not been implemented'
    spec = importlib.util.spec_from_file_location('bounded_adapter', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def plan(a):
    return {'schema_version': 1, 'guard_files': {}, 'rows': [
        {'qid': f'Q{i}', 'baseline': b, 'status': 'NOT_ATTEMPTED',
         'payload': a.make_payload('source is untrusted', 'doc', 'question',
                                   [{'start': 0, 'end': 4, 'text': 'text'}])}
        for i in range(9) for b in ('B1', 'B2', 'B3')]}


def target(tmp_path):
    return tmp_path / 'docs/superpowers/plans/scope-pilot/api-runs/fixture'


def response(**changes):
    body = {'id': 'fixture', 'model': 'deepseek-v4-pro', 'system_fingerprint': 'fixture',
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'answer'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
    body.update(changes)
    return body


def test_fixed_payload():
    a = adapter()
    payload = a.make_payload('system', 'doc', 'query', [])
    assert payload['model'] == 'deepseek-v4-pro'
    assert payload['thinking'] == {'type': 'disabled'}
    assert payload['temperature'] == 0 and payload['max_tokens'] == 2048
    assert payload['stream'] is False and 'extra_body' not in payload
    assert 'items' not in payload['messages'][1]['content']


def test_dry_run_does_not_dispatch(tmp_path):
    a = adapter()
    def forbidden(request):
        pytest.fail('dry run dispatched')
    result = a.run(plan(a), tmp_path, target(tmp_path), transport=httpx.MockTransport(forbidden))
    assert result == {'NOT_ATTEMPTED': 27}
    assert (target(tmp_path) / 'plan.json').exists()


def test_success_is_journaled_without_auth(tmp_path):
    a = adapter()
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url == 'https://api.deepseek.com/chat/completions'
        journal = (target(tmp_path) / 'journal.jsonl').read_text()
        assert 'ATTEMPT_INTENT' in journal
        return httpx.Response(200, json=response())
    assert a.run(plan(a), tmp_path, target(tmp_path), execute=True,
                 credential='fixture-secret', transport=httpx.MockTransport(handler)) == {'SUCCESS': 27}
    assert len(calls) == 27
    for file in target(tmp_path).iterdir():
        assert 'fixture-secret' not in file.read_text()
    assert json.loads((target(tmp_path) / '000-response.json').read_text())['usage']['total_tokens'] == 2


@pytest.mark.parametrize('case', ['redirect', 'http', 'network', 'model', 'length', 'empty', 'malformed', 'reflected'])
def test_failure_stops_without_retry_or_secret(tmp_path, case):
    a = adapter()
    calls = []
    def handler(request):
        calls.append(request)
        if case == 'network':
            raise httpx.ConnectError('fixture-secret', request=request)
        if case == 'redirect':
            return httpx.Response(302, headers={'location': 'https://evil.invalid'})
        if case == 'http':
            return httpx.Response(401, text='fixture-secret')
        if case == 'malformed':
            return httpx.Response(200, text='not valid json')
        body = response()
        if case == 'model': body['model'] = 'another-model'
        if case == 'length': body['choices'][0]['finish_reason'] = 'length'
        if case == 'empty': body['choices'][0]['message']['content'] = ''
        if case == 'reflected': body['choices'][0]['message']['content'] = 'fixture-secret'
        return httpx.Response(200, json=body)
    result = a.run(plan(a), tmp_path, target(tmp_path), execute=True,
                   credential='fixture-secret', transport=httpx.MockTransport(handler))
    assert len(calls) == 1 and result['NOT_ATTEMPTED'] == 26
    assert result.get('SUCCESS', 0) == 0
    if case == 'malformed':
        statuses = json.loads((target(tmp_path) / 'final-statuses.json').read_text())
        assert statuses[0]['error'] == 'MALFORMED_RESPONSE'
    for file in target(tmp_path).iterdir():
        assert 'fixture-secret' not in file.read_text()


def test_output_containment_and_existing_refusal(tmp_path):
    a = adapter()
    with pytest.raises(a.PilotError): a.run(plan(a), tmp_path, tmp_path / 'outside')
    a.run(plan(a), tmp_path, target(tmp_path))
    with pytest.raises(a.PilotError): a.run(plan(a), tmp_path, target(tmp_path))


def test_request_budget_and_tampered_model_refused(tmp_path):
    a = adapter()
    p = plan(a)
    p['rows'].append(p['rows'][0])
    with pytest.raises(a.PilotError): a.run(p, tmp_path, target(tmp_path))
    p = plan(a)
    p['rows'][0]['payload']['model'] = 'another-model'
    with pytest.raises(a.PilotError): a.run(p, tmp_path, target(tmp_path))


def test_source_redaction_preserves_surviving_offsets():
    a = adapter()
    source = 'first\n参赛编号：002196\nlast'
    filtered, excluded = a.filter_source(source)
    assert '002196' not in filtered and '参赛编号' not in filtered
    assert len(filtered) == len(source)
    assert filtered.index('last') == source.index('last')
    assert excluded[0]['reason'] == 'participant_number_line'


def test_guard_drift_rejected(tmp_path):
    a = adapter()
    p = plan(a)
    p['guard_files'] = {'missing.py': '0' * 64}
    with pytest.raises(a.PilotError): a.run(p, tmp_path, target(tmp_path))


def test_credentials_select_only_approved_langextract_key(tmp_path, monkeypatch):
    import dotenv
    a = adapter()
    seen = []
    def synthetic_values(path, interpolate):
        seen.append((path, interpolate))
        return {'LANGEXTRACT_API_KEY': 'approved-fixture-key',
                'DEEPSEEK_API_KEY': 'unapproved-fixture-key',
                'LANGEXTRACT_BASE_URL': 'https://api.deepseek.com'}
    monkeypatch.setattr(dotenv, 'dotenv_values', synthetic_values)
    assert a.credentials(tmp_path) == 'approved-fixture-key'
    assert seen == [(tmp_path / 'backend/.env', False)]


def test_malformed_json_without_secret_stops_once(tmp_path):
    a = adapter()
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, text='{broken-json')
    counts = a.run(plan(a), tmp_path, target(tmp_path), execute=True,
                   credential='fixture-secret', transport=httpx.MockTransport(handler))
    assert len(calls) == 1 and counts == {'FAILED': 1, 'NOT_ATTEMPTED': 26}
    statuses = json.loads((target(tmp_path) / 'final-statuses.json').read_text())
    assert statuses[0]['error'] == 'MALFORMED_RESPONSE'
    assert not (target(tmp_path) / '000-response.json').exists()


@pytest.mark.parametrize('choices', [None, {}, [], [[]], [None],
                                    [{'message': None}], [{'message': []}],
                                    [{'message': {'content': 'answer'}}]])
def test_malformed_nested_response_is_failed_and_finalized(tmp_path, choices):
    a = adapter()
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response(choices=choices))
    counts = a.run(plan(a), tmp_path, target(tmp_path), execute=True,
                   credential='fixture-secret', transport=httpx.MockTransport(handler))
    assert len(calls) == 1 and counts == {'FAILED': 1, 'NOT_ATTEMPTED': 26}
    statuses = json.loads((target(tmp_path) / 'final-statuses.json').read_text())
    assert statuses[0]['error'] == 'MALFORMED_RESPONSE'
    assert not (target(tmp_path) / '000-response.json').exists()


def test_guard_rechecked_before_every_dispatch(tmp_path):
    a = adapter()
    protected = tmp_path / 'protected.txt'
    protected.write_text('frozen', encoding='utf-8')
    p = plan(a)
    p['guard_files'] = {'protected.txt': a.digest(protected.read_bytes())}
    calls = []
    def handler(request):
        calls.append(request)
        protected.write_text('drifted', encoding='utf-8')
        return httpx.Response(200, json=response())
    counts = a.run(p, tmp_path, target(tmp_path), execute=True,
                   credential='fixture-secret', transport=httpx.MockTransport(handler))
    assert len(calls) == 1 and counts == {'SUCCESS': 1, 'NOT_ATTEMPTED': 26}


def test_secret_payload_refused_before_artifact_creation(tmp_path):
    a = adapter()
    p = plan(a)
    p['rows'][0]['payload']['messages'][0]['content'] = 'fixture-secret'
    with pytest.raises(a.PilotError):
        a.run(p, tmp_path, target(tmp_path), execute=True, credential='fixture-secret')
    assert not target(tmp_path).exists()


def test_preparation_uses_contexts_and_never_gold_in_payload(tmp_path):
    import yaml
    a = adapter()
    local = tmp_path / a.PILOT_DIR
    local.mkdir(parents=True)
    shutil.copyfile(HERE.parents[1] / a.PILOT_DIR / 'pilot.py', local / 'pilot.py')
    source = 'begin\n参赛编号：002196\nsupported fact\nend'
    source_path = tmp_path / 'source.md'
    source_path.write_text(source, encoding='utf-8')
    gold = {'documents': {'D': {'path': 'source.md', 'sha256': a.digest(source_path.read_bytes())}},
            'questions': [{'id': f'Q{i}', 'doc': 'D', 'query': 'supported',
                           'scope': {'kind': 'section', 'start': 'begin', 'end': 'end'},
                           'items': [{'id': 'NEVER_TRANSMIT_GOLD_ID', 'label': 'gold_label',
                                      'value': 'gold_value', 'unit': 'gold_unit',
                                      'condition': 'gold_condition', 'role': 'gold_role',
                                      'anchor': 'supported fact'}]} for i in range(9)]}
    (local / 'gold.yaml').write_text(yaml.safe_dump(gold), encoding='utf-8')
    (local / 'inputs-B2.json').write_text(json.dumps({'system_instruction': 'fixture system'}), encoding='utf-8')
    paths = ['source.md'] + [(a.PILOT_DIR / n).as_posix() for n in ('pilot.py', 'gold.yaml', 'inputs-B2.json')]
    manifest_path = local / 'manifest.json'
    manifest_path.write_text(json.dumps({'schema_version': 1, 'guard_files': {
        name: a.digest((tmp_path / name).read_bytes()) for name in paths}}), encoding='utf-8')
    result = a.prepare(tmp_path, manifest_path)
    assert len(result['rows']) == 27
    assert result['source_exclusions']['D']
    for row in result['rows']:
        body = a.canonical(row['payload'])
        assert 'NEVER_TRANSMIT_GOLD_ID' not in body
        assert 'gold_value' not in body and '002196' not in body
        content = json.loads(row['payload']['messages'][1]['content'])
        for span in content['source_contexts']:
            assert source[span['start']:span['end']] == span['text']
    manifest_path.write_text('{}', encoding='utf-8')
    with pytest.raises(a.PilotError, match='MANIFEST_HASH_DRIFT'):
        a.run(result, tmp_path, target(tmp_path))
