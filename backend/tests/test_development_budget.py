import json
import httpx
import pytest
from research.development_budget import BudgetGuard, BudgetLimits, BudgetStopped


def payload():
    return {'model': 'deepseek-flash', 'messages': [{'role': 'user', 'content': '实际输入中文'}], 'max_tokens': 2048, 'thinking': {'type': 'disabled'}}


def response():
    return {'model': 'deepseek-flash', 'choices': [{'finish_reason': 'stop', 'message': {'content': '答案'}}], 'usage': {'prompt_tokens': 8, 'completion_tokens': 2, 'total_tokens': 10}}


def test_guard_records_sdk_wire_payload_and_blocks_cumulative_attempts(tmp_path):
    seen = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(200, json=response()))[1]))
    guard = BudgetGuard(tmp_path, 'secret-test', BudgetLimits(total_attempts=1))
    with guard.install(), guard.phase('A', 'Q1'):
        client.post('https://api.deepseek.com/chat/completions', json=payload())
        with pytest.raises(BudgetStopped):
            client.post('https://api.deepseek.com/chat/completions', json=payload())
    assert len(seen) == 1
    ledger = json.loads((tmp_path / 'ledger.json').read_text(encoding='utf-8'))
    assert ledger['actual_attempts'] == 1
    assert ledger['input_bytes'] == len(json.dumps(payload(), ensure_ascii=False, separators=(',', ':')).encode())
    assert ledger['records'][0]['usage']['total_tokens'] == 10


@pytest.mark.parametrize('change', [{'model': 'other'}, {'max_tokens': 9999}, {'thinking': {'type': 'enabled'}}])
def test_rejects_wrong_wire_parameters_before_send(tmp_path, change):
    guard = BudgetGuard(tmp_path, 'secret-test')
    data = payload() | change
    with guard.install(), guard.phase('A'):
        with pytest.raises(BudgetStopped):
            httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('network reached'))).post('https://api.deepseek.com/chat/completions', json=data)
    assert guard.actual_attempts == 0


def test_missing_usage_closes_guard_and_error_body_is_redacted(tmp_path):
    data = response(); data.pop('usage'); data['error'] = 'secret-test'
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('P0'):
        with pytest.raises(BudgetStopped):
            httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert guard.closed
    assert 'secret-test' not in ''.join(p.read_text(encoding='utf-8') for p in tmp_path.glob('*.json'))
    assert json.loads((tmp_path / 'ledger.json').read_text(encoding='utf-8'))['records'][0]['cost_status'] == 'UNKNOWN'


def test_input_bytes_limit_and_unapproved_host_do_not_send(tmp_path):
    for i, url in enumerate(('https://api.deepseek.com/chat/completions', 'https://example.com/chat/completions')):
        guard = BudgetGuard(tmp_path / str(i), 'secret-test', BudgetLimits(input_bytes=1))
        with guard.install(), guard.phase('A'), pytest.raises(BudgetStopped):
            httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('sent'))).post(url, json=payload())
        assert guard.actual_attempts == 0


def test_persisted_ledger_does_not_reset_between_commands(tmp_path):
    limits = BudgetLimits(total_attempts=1)
    with BudgetGuard(tmp_path, 'secret-test', limits).install() as first, first.phase('a'):
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response()))).post('https://api.deepseek.com/chat/completions', json=payload())
    second = BudgetGuard(tmp_path, 'secret-test', limits)
    with second.install(), second.phase('p0'), pytest.raises(BudgetStopped):
        httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('sent twice'))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert second.actual_attempts == 1


def test_guard_refreshes_ledger_after_acquiring_process_lock(tmp_path):
    limits = BudgetLimits(total_attempts=1)
    first = BudgetGuard(tmp_path, 'secret-test', limits)
    stale = BudgetGuard(tmp_path, 'secret-test', limits)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response())))
    with first.install(), first.phase('a'):
        client.post('https://api.deepseek.com/chat/completions', json=payload())
    with stale.install(), stale.phase('a'), pytest.raises(BudgetStopped):
        client.post('https://api.deepseek.com/chat/completions', json=payload())
    assert stale.actual_attempts == 1


def test_unknown_pending_request_is_not_automatically_resumed(tmp_path):
    first = BudgetGuard(tmp_path, 'secret-test')
    with first.phase('a'):
        first._begin('https://api.deepseek.com/chat/completions', json.dumps(payload()).encode(), 'httpx')
    resumed = BudgetGuard(tmp_path, 'secret-test')
    assert resumed.closed and resumed.actual_attempts == 1


def test_requests_retry_is_refused_after_first_failure(tmp_path, monkeypatch):
    import requests
    calls = []
    def upstream(session, request, **kwargs):
        calls.append(kwargs)
        result = requests.Response(); result.status_code = 500
        result._content = b'{"error":"secret-test"}'
        return result
    monkeypatch.setattr(requests.Session, 'send', upstream)
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('p0'):
        for _ in range(2):
            with pytest.raises(BudgetStopped):
                requests.post('https://api.deepseek.com/chat/completions', json=payload())
    assert len(calls) == 1 and calls[0]['allow_redirects'] is False
    assert guard.actual_attempts == 1
    assert guard.state['records'][-1]['status'] == 'NOT_SENT'


def test_sdk_factory_limits_reach_real_wire_payload(tmp_path, monkeypatch):
    import langextract.factory as factory
    from research.development_isolation import bounded_langextract
    wire = []
    from research.development_budget import openai_transport_module
    sdk_http = openai_transport_module()
    def offline_transport(request):
        wire.append(request)
        data = response(); data['choices'][0]['message']['content'] = '{"extractions": []}'
        return sdk_http.Response(200, json=data, request=request)
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('index'), bounded_langextract(http_client_factory=lambda: sdk_http.Client(transport=sdk_http.MockTransport(offline_transport), trust_env=False)) as details:
        model = factory.create_model(factory.ModelConfig(model_id='deepseek-flash', provider='openai', provider_kwargs={'api_key': 'secret-test', 'base_url': 'https://api.deepseek.com'}))
        result = model._process_single_prompt('全源真实SDK参数测试', model._extra_kwargs)
    data = json.loads(wire[0].content)
    assert data['max_tokens'] == 4096
    assert data['thinking'] == {'type': 'disabled'}
    assert len(wire) == 1 and details[0]['sdk_max_retries'] == 0
    assert model.max_workers == 1
    assert result.output == '{"extractions": []}'
    assert guard.actual_attempts == 1


def test_truncation_closes_profile_with_known_usage(tmp_path):
    data = response(); data['choices'][0]['finish_reason'] = 'length'
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('a'), pytest.raises(BudgetStopped):
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert guard.closed
    assert guard.state['records'][0]['cost_status'] == 'KNOWN'


def test_expired_window_is_refused_before_send(tmp_path):
    guard = BudgetGuard(tmp_path, 'secret-test')
    guard.state['started_epoch'] = 0
    guard._save()
    with guard.install(), guard.phase('a'), pytest.raises(BudgetStopped):
        httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('expired sent'))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert guard.actual_attempts == 0


def test_error_json_body_is_omitted_entirely(tmp_path):
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('a'), pytest.raises(BudgetStopped):
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={'error': 'private-upstream-diagnostic'}))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert 'private-upstream-diagnostic' not in (tmp_path / 'ledger.json').read_text(encoding='utf-8')


@pytest.mark.parametrize('content', ['', '  ', 'secret-test'])
def test_empty_or_secret_success_content_is_not_returned(tmp_path, content):
    data = response(); data['choices'][0]['message']['content'] = content
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('a'), pytest.raises(BudgetStopped):
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))).post('https://api.deepseek.com/chat/completions', json=payload())
    assert guard.closed


@pytest.mark.parametrize('bad', [[], {'choices': [None]}, {'choices': {}}, {'choices': [{'message': None}]}, {'choices': [{'message': {'content': 3}}]}])
def test_malformed_response_closes_guard_and_forbids_followup(tmp_path, bad):
    guard = BudgetGuard(tmp_path, 'secret-test')
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=bad)))
    with guard.install(), guard.phase('a'):
        with pytest.raises(BudgetStopped): client.post('https://api.deepseek.com/chat/completions', json=payload())
        assert guard.closed
        with pytest.raises(BudgetStopped): client.post('https://api.deepseek.com/chat/completions', json=payload())
    assert guard.actual_attempts == 1


def test_actual_sdk_async_transport_is_accounted(tmp_path):
    from research.development_budget import openai_transport_module
    sdk_http = openai_transport_module()
    guard = BudgetGuard(tmp_path, 'secret-test')
    async def run():
        async with sdk_http.AsyncClient(transport=sdk_http.MockTransport(lambda r: sdk_http.Response(200, json=response()))) as client:
            with guard.install(), guard.phase('a'):
                await client.post('https://api.deepseek.com/chat/completions', json=payload())
    # MockTransport completes without I/O suspension. Drive the coroutine
    # directly; Windows sandbox loop self-pipe sockets are unavailable here.
    with pytest.raises(StopIteration): run().send(None)
    assert guard.actual_attempts == 1
    assert guard.state['records'][0]['transport'] == sdk_http.__name__ + '_async'


def test_actual_sdk_transport_refuses_foreign_host_without_retry(tmp_path):
    from research.development_budget import openai_transport_module
    sdk_http = openai_transport_module()
    guard = BudgetGuard(tmp_path, 'secret-test')
    client = sdk_http.Client(transport=sdk_http.MockTransport(lambda r: pytest.fail('SDK foreign host reached')))
    with guard.install(), guard.phase('index'), pytest.raises(BudgetStopped):
        client.post('https://example.com/chat/completions', json=payload())
    assert guard.closed and guard.actual_attempts == 0


def test_exact_wire_checksums_survive_whitespace_and_unicode_escapes(tmp_path):
    import hashlib
    raw_request = json.dumps(payload(), ensure_ascii=True, indent=3).encode('utf-8')
    raw_response = json.dumps(response(), ensure_ascii=True, indent=2).encode('utf-8')
    guard = BudgetGuard(tmp_path, 'secret-test')
    with guard.install(), guard.phase('a'):
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw_response))).post(
            'https://api.deepseek.com/chat/completions', content=raw_request, headers={'Content-Type': 'application/json'})
    record = guard.state['records'][0]
    for kind, raw in [('request', raw_request), ('response', raw_response)]:
        wire = record[kind + '_wire_utf8'].encode('utf-8')
        assert wire == raw
        assert hashlib.sha256(wire).hexdigest() == record[kind + '_sha256']
        assert json.loads(wire) == record[kind]
        assert wire != json.dumps(record[kind], ensure_ascii=False).encode('utf-8')
    assert len(record['request_wire_utf8'].encode('utf-8')) == record['input_bytes']
