"""Exercise secrecy and response-validation boundaries without any network."""
import json
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ns = runpy.run_path(str(HERE / 'profile.py'))
secret = 'offline-sentinel-not-a-real-key'
checks = []
base = {'LANGEXTRACT_API_KEY': secret, 'LANGEXTRACT_BASE_URL': 'https://api.deepseek.com',
        'LANGEXTRACT_MODEL_ID': 'deepseek-chat'}

class Response:
    def __init__(self, code=200, text='safe', data=None):
        self.status_code, self.text, self.data = code, text, data
    def json(self):
        return self.data

good = {'model': 'deepseek-chat', 'choices': [{'message': {'content': 'cited text [c1]'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}}
with tempfile.TemporaryDirectory(dir=HERE, prefix='offline-check-') as temp:
    p = Path(temp)
    req, resp = p / 'request.json', p / 'response.json'
    req.write_text(json.dumps({'model': 'deepseek-chat', 'messages': [], 'max_tokens': 2048}), encoding='utf-8')
    for name, config, response, expected, should_call in [
        ('foreign_origin_blocked', {**base, 'LANGEXTRACT_BASE_URL': 'https://example.org'}, Response(), 'CONFIG_MISMATCH', False),
        ('wrong_model_blocked', {**base, 'LANGEXTRACT_MODEL_ID': 'other'}, Response(), 'CONFIG_MISMATCH', False),
        ('http_error_body_omitted', base, Response(429, secret), 'HTTP_ERROR', True),
        ('secret_in_success_rejected', base, Response(200, secret, good), 'SECRET_RESPONSE_REJECTED', True),
        ('valid_usage_accepted', base, Response(data=good), 'SUCCESS', True),
        ('inconsistent_usage_rejected', base, Response(data={**good, 'usage': {'prompt_tokens':10,'completion_tokens':3,'total_tokens':99}}), 'INVALID_OR_TRUNCATED_RESPONSE', True),
        ('truncation_rejected', base, Response(data={**good, 'choices':[{'message':{'content':'partial'},'finish_reason':'length'}]}), 'INVALID_OR_TRUNCATED_RESPONSE', True),
    ]:
        with patch('dotenv.dotenv_values', return_value=config), patch('requests.post', return_value=response) as post:
            ns['worker'](req, resp)
        result = json.loads(resp.read_text(encoding='utf-8'))
        assert result['status'] == expected and post.called == should_call, name
        assert secret not in resp.read_text(encoding='utf-8'), name
        if post.called:
            assert post.call_args.kwargs['allow_redirects'] is False
        checks.append({'check': name, 'status':'PASS'})
    with patch('dotenv.dotenv_values', return_value=base), patch('requests.post', side_effect=RuntimeError(secret)):
        ns['worker'](req, resp)
    assert secret not in resp.read_text(encoding='utf-8')
    assert json.loads(resp.read_text(encoding='utf-8'))['send_status'] == 'REQUEST_ATTEMPTED_DELIVERY_UNKNOWN'
    checks.append({'check':'exception_secret_omitted_and_delivery_unknown','status':'PASS'})
ns['save'](HERE / 'offline-verification.json', {'status':'PASS', 'network_calls':0,'real_credentials_read':False,'checks':checks})
print(json.dumps({'status':'PASS','checks':len(checks),'network_calls':0}))
