"""Real JWT, JSON persistence and ASGI endpoint behavior; OIDC HTTP is a boundary."""
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_p0_resource_routes import resource_app  # noqa: F401


@pytest.fixture
def identity_app(resource_app, monkeypatch):
    from routes import auth, tenants, bot
    from services import auth_service, tenant_service, audit_logger, api_key_manager
    from middleware.jwt_middleware import create_jwt_middleware
    root = resource_app.base / 'identities'
    for name in ('APP_ENV', 'ENVIRONMENT', 'ENV', 'NODE_ENV'):
        monkeypatch.setenv(name, 'test')
    monkeypatch.setenv('AUTH_PROVIDER', 'local')
    monkeypatch.setenv('AUTH_ALLOW_ANONYMOUS', 'false')
    monkeypatch.delenv('ADMIN_API_KEY', raising=False)
    for attr, value in [('TENANTS_DIR', root), ('ORGS_DIR', root / 'orgs'),
                        ('PROJECTS_DIR', root / 'projects'), ('MEMBERS_DIR', root / 'members')]:
        monkeypatch.setattr(tenant_service, attr, value)
    monkeypatch.setattr(tenant_service, '_service', None)
    tenant = tenant_service.get_tenant_service()
    monkeypatch.setattr(audit_logger, '_audit', audit_logger.AuditLogger(root / 'audit'))
    # Never allow JWT fallback to inspect production API-key records.
    monkeypatch.setattr(api_key_manager, '_manager', api_key_manager.ApiKeyManager(root / 'keys'))
    app = FastAPI()
    from errors import register_exception_handlers
    register_exception_handlers(app)
    app.middleware('http')(create_jwt_middleware())
    for module in (auth, tenants, bot):
        app.include_router(module.router, prefix='/api/v1')
    return SimpleNamespace(client=TestClient(app, raise_server_exceptions=False),
                           headers=resource_app.headers, service=auth_service.get_auth_service(),
                           tenant=tenant, root=root)


def test_local_login_refresh_and_disable(identity_app, monkeypatch):
    env = identity_app
    assert env.client.get('/api/v1/auth/login').json()['provider'] == 'local'
    assert env.service.get_login_url() == '/login'
    assert env.client.post('/api/v1/auth/login', json={'username': 'new'}).status_code == 401
    monkeypatch.setenv('AUTH_ALLOW_ANONYMOUS', 'true')
    result = env.client.post('/api/v1/auth/login', json={'username': 'new'}).json()
    from middleware.jwt_middleware import decode_token
    user_id = decode_token(result['access_token'])['sub']
    assert env.service.get_user(user_id).last_login
    again = env.client.post('/api/v1/auth/login', json={'username': 'new'}).json()
    assert decode_token(again['access_token'])['sub'] == user_id
    assert env.client.post('/api/v1/auth/refresh', json={'refresh_token': result['refresh_token']}).status_code == 200
    for token in ('broken', result['access_token']):
        assert env.client.post('/api/v1/auth/refresh', json={'refresh_token': token}).status_code == 401
    assert env.client.delete(f'/api/v1/users/{user_id}', headers=env.headers()).json()['status'] == 'disabled'
    assert env.client.post('/api/v1/auth/refresh', json={'refresh_token': result['refresh_token']}).status_code == 401
    assert env.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + result['access_token']}).status_code == 401


@pytest.mark.parametrize('body', [{'provider': 'oidc', 'username': 'alice'}, {'username': ''}, {}])
def test_login_rejects_unsupported_or_missing_identity(identity_app, body):
    assert identity_app.client.post('/api/v1/auth/login', json=body).status_code == 401


@pytest.mark.parametrize('method,path,body', [
    ('get', '/users', None), ('put', '/users/alice/roles', {'roles': ['admin']}),
    ('delete', '/users/alice', None), ('post', '/orgs', {'name': 'Forbidden', 'slug': 'no'}),
])
@pytest.mark.parametrize('principal', [None, 'alice'])
def test_administration_rejects_nonadmins(identity_app, method, path, body, principal):
    kwargs = {'headers': identity_app.headers(principal)} if principal else {}
    if body is not None:
        kwargs['json'] = body
    response = identity_app.client.request(method, '/api/v1' + path, **kwargs)
    assert response.status_code == 403
    assert identity_app.service.get_user('alice').roles == ['viewer']
    assert identity_app.tenant.list_orgs() == []


def test_user_admin_persistence_and_profile(identity_app):
    env = identity_app
    from services import auth_service
    (auth_service.USERS_DIR / 'corrupt.json').write_text('{', encoding='utf-8')
    assert env.service.get_user('corrupt') is None
    assert env.client.get('/api/v1/auth/me').status_code == 401
    assert env.client.get('/api/v1/auth/me', headers=env.headers('alice')).json()['user_id'] == 'alice'
    result = env.client.get('/api/v1/users', headers=env.headers()).json()['users']
    assert {u['user_id'] for u in result} == {'admin', 'alice', 'bob', 'unknown'}
    response = env.client.put('/api/v1/users/alice/roles', headers=env.headers(), json={'roles': ['editor', 'invalid']})
    assert response.status_code == 200
    assert response.json()['user']['roles'] == ['editor']
    assert env.service.get_user('alice').roles == ['editor']
    assert env.client.post('/api/v1/auth/logout', headers=env.headers('alice')).json() == {'status': 'logged_out'}
    assert env.client.post('/api/v1/auth/logout').status_code == 200
    for method, path, body in [('put', '/users/missing/roles', {'roles': []}), ('delete', '/users/missing', None)]:
        kwargs = {'headers': env.headers()}
        if body is not None:
            kwargs['json'] = body
        assert env.client.request(method, '/api/v1' + path, **kwargs).status_code == 404


@pytest.mark.parametrize('provider_failure', [False, True])
def test_oidc_state_consumption_and_redirect(identity_app, monkeypatch, provider_failure):
    env = identity_app
    monkeypatch.setenv('AUTH_PROVIDER', 'oidc')
    monkeypatch.setenv('OIDC_ISSUER', 'https://identity.invalid')
    import requests
    calls = []
    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            if provider_failure:
                raise requests.HTTPError('provider unavailable')
        def json(self):
            return self.payload
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response({'access_token': 'provider-boundary-token'})
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: Response({'sub': 'alice', 'preferred_username': 'Alice SSO', 'email': 'alice@example.invalid'}))
    info = env.client.get('/api/v1/auth/login').json()
    assert info['provider'] == 'oidc'
    state = parse_qs(urlparse(info['login_url']).query)['state'][0]
    assert env.client.get('/api/v1/auth/callback', params={'code': 'code', 'state': 'missing'}).status_code == 401
    response = env.client.get('/api/v1/auth/callback', params={'code': 'code', 'state': state}, follow_redirects=False)
    assert response.status_code == (401 if provider_failure else 302)
    assert calls[0][1]['data']['code'] == 'code'
    assert env.client.get('/api/v1/auth/callback', params={'code': 'code', 'state': state}).status_code == 401
    if not provider_failure:
        tokens = parse_qs(urlparse(response.headers['location']).query)
        from middleware.jwt_middleware import decode_token
        assert decode_token(tokens['access_token'][0])['sub'] == 'alice'
        assert env.service.get_user('alice').username == 'Alice SSO'
        assert env.service.get_user('alice').roles == ['viewer']
        new = env.service._upsert_oauth_user({'sub': 'oidc-new', 'name': 'SSO'})
        assert new.display_name == 'SSO' and new.roles == ['viewer']
    assert env.service.login_local('alice', '') is None


def create_org(env, name='Example'):
    response = env.client.post('/api/v1/orgs', headers=env.headers(), json={'name': name, 'slug': name.lower()})
    assert response.status_code == 200, response.text
    return response.json()['org']['org_id']


def test_tenant_end_to_end_members_projects_and_tombstones(identity_app):
    env = identity_app
    org = create_org(env)
    other = create_org(env, 'Other')
    base = f'/api/v1/orgs/{org}'
    assert env.client.get('/api/v1/orgs').status_code == 401
    assert len(env.client.get('/api/v1/orgs', headers=env.headers()).json()['orgs']) == 2
    assert env.client.get(base).json()['org']['name'] == 'Example'
    assert env.client.get('/api/v1/orgs/missing').status_code == 404
    invited = env.client.post(base + '/members', headers=env.headers(), json={'user_id': 'alice', 'role': 'org_admin'})
    assert invited.status_code == 200
    membership = invited.json()['member']['membership_id']
    duplicate = env.client.post(base + '/members', headers=env.headers(), json={'user_id': 'alice', 'role': 'viewer'})
    assert duplicate.json()['member']['membership_id'] == membership
    assert env.client.get('/api/v1/orgs', headers=env.headers('alice')).json()['orgs'][0]['org_id'] == org
    assert env.client.put(base, headers=env.headers('alice'), json={'name': 'Updated', 'ignored': True}).json()['org']['name'] == 'Updated'
    created = env.client.post(base + '/projects', headers=env.headers('alice'), json={'name': 'P'})
    assert created.status_code == 200
    project = created.json()['project']['project_id']
    path = base + '/projects/' + project
    assert env.client.put(path, headers=env.headers('alice'), json={'description': 'Changed'}).json()['project']['description'] == 'Changed'
    assert len(env.client.get(base + '/projects').json()['projects']) == 1
    assert env.client.get(f'/api/v1/orgs/{other}/projects').json()['projects'] == []
    assert env.client.post(path + '/archive', headers=env.headers('alice')).json()['project']['is_archived'] is True
    assert env.client.get(base + '/members').json()['members'][0]['user_id'] == 'alice'
    assert env.client.put(base + '/members/alice/role', headers=env.headers(), json={'role': 'viewer'}).json()['member']['role'] == 'viewer'
    assert env.client.put(base, headers=env.headers('alice'), json={'name': 'Denied'}).status_code == 403
    assert env.client.delete(base + '/members/alice', headers=env.headers()).json()['status'] == 'removed'
    assert env.client.get(base + '/members').json()['members'] == []
    assert env.tenant.get_member(org, 'alice') is None
    assert env.tenant.get_user_orgs('alice')[0]['org_id'] == 'default'


@pytest.mark.parametrize('suffix,method,body', [
    ('', 'put', {'name': 'x'}), ('/projects', 'post', {'name': 'x'}),
    ('/members', 'post', {'user_id': 'alice'}),
    ('/members/alice/role', 'put', {'role': 'viewer'}),
    ('/members/alice', 'delete', None), ('/projects/no/archive', 'post', None),
    ('/projects/no', 'put', {'name': 'x'}),
])
def test_tenant_missing_resources_and_permission_matrix(identity_app, suffix, method, body):
    env = identity_app
    path = '/api/v1/orgs/missing' + suffix
    for principal, expected in [(None, 401), ('alice', 403), ('admin', 404)]:
        kwargs = {'headers': env.headers(principal)} if principal else {}
        if body is not None:
            kwargs['json'] = body
        response = env.client.request(method, path, **kwargs)
        assert response.status_code == expected, response.text


def test_tenant_corrupt_json_inactive_org_and_project_deletion(identity_app):
    env = identity_app
    from services import tenant_service as ts
    for folder in (ts.ORGS_DIR, ts.PROJECTS_DIR, ts.MEMBERS_DIR):
        (folder / 'corrupt.json').write_text('{', encoding='utf-8')
    (ts.MEMBERS_DIR / 'invalid.json').write_text('{}', encoding='utf-8')
    assert env.tenant.list_orgs() == []
    assert env.tenant.list_projects() == []
    assert env.tenant.list_members('missing') == []
    assert env.tenant.get_user_orgs('nobody')[0]['org_id'] == 'default'
    org = create_org(env)
    assert env.tenant.delete_org('missing') is False
    assert env.tenant.delete_org(org) is True
    assert env.tenant.delete_org(org) is True
    assert env.tenant.get_org(org) is None
    assert env.tenant.update_org(org, {'name': 'revive'}) is None
    assert env.tenant.list_orgs() == []
    assert env.tenant.delete_project('missing') is False
    assert env.tenant.update_project('missing', {'name': 'absent'}) is None


def test_cross_org_project_update_is_not_found(identity_app):
    env = identity_app
    from models import ProjectCreate
    org = create_org(env)
    other = create_org(env, 'Other')
    project = env.tenant.create_project(other, ProjectCreate(name='Foreign'), 'admin')
    response = env.client.put(f'/api/v1/orgs/{org}/projects/{project.project_id}', headers=env.headers(), json={'name': 'changed'})
    assert response.status_code == 404
    assert env.tenant.get_project(project.project_id).name == 'Foreign'
    assert env.tenant.delete_project(project.project_id) is True
    assert env.tenant.get_project(project.project_id) is None


@pytest.fixture
def feishu_boundary(identity_app, monkeypatch):
    """Substitute only outbound provider HTTP; real client/card/signature code runs."""
    import requests
    for key in ('FEISHU_APP_ID', 'FEISHU_APP_SECRET', 'FEISHU_VERIFICATION_TOKEN', 'FEISHU_ENCRYPT_KEY', 'FEISHU_ALERT_CHAT_ID'):
        monkeypatch.delenv(key, raising=False)
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'tenant_access_token': 'test-provider-token', 'data': {'message_id': 'reply'}}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(requests, 'post', post)
    return calls


def test_bot_unconfigured_config_and_challenges(identity_app, feishu_boundary):
    client = identity_app.client
    assert client.get('/api/v1/bot/config').json()['feishu'] == {'configured': False, 'app_id': '', 'verification_configured': False}
    assert client.post('/api/v1/bot/feishu', json={'type': 'url_verification', 'challenge': 'abc'}).json() == {'challenge': 'abc'}
    assert client.post('/api/v1/bot/feishu', json={}).json() == {'status': 'ok'}
    assert client.post('/api/v1/bot/feishu/alert', json={'alerts': [{}]}).json()['alert_count'] == 1
    assert client.put('/api/v1/bot/config/feishu', json={'app id': 'ignored'}).json()['status'] == 'config_note'
    assert client.put('/api/v1/bot/config/feishu', json={}).status_code == 200
    for method, path in [('put', '/api/v1/bot/config/unknown'), ('post', '/api/v1/bot/config/unknown/test'), ('post', '/api/v1/bot/config/feishu/test')]:
        assert client.request(method, path, json={}).status_code == 400
    # A malformed text event triggers the real handler exception path.
    bad = {'event': {'type': 'im.message.receive_v1', 'message': {'msg_type': 'text', 'content': '{'}}}
    assert client.post('/api/v1/bot/feishu', json=bad).json() == {'status': 'ok'}
    assert feishu_boundary == []


@pytest.mark.parametrize('signature', ['valid', 'invalid', 'missing'])
@pytest.mark.parametrize('verification', [False, True])
def test_bot_signature_verification(identity_app, feishu_boundary, monkeypatch, signature, verification):
    import hashlib
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', 'verification-fixture')
    monkeypatch.setenv('FEISHU_ENCRYPT_KEY', 'encrypt-fixture')
    event = {'type': 'url_verification', 'challenge': 'event-challenge'}
    body = json.dumps(event if verification else {'event': event}).encode()
    headers = {'Content-Type': 'application/json'}
    if signature != 'missing':
        digest = hashlib.sha256(b'123nonceencrypt-fixture' + body).hexdigest()
        headers.update({'X-Lark-Request-Timestamp': '123', 'X-Lark-Request-Nonce': 'nonce',
                        'X-Lark-Signature': digest if signature == 'valid' else 'invalid'})
    response = identity_app.client.post('/api/v1/bot/feishu', content=body, headers=headers)
    assert response.status_code == {'invalid': 403, 'missing': 401, 'valid': 200}[signature]
    if signature == 'valid':
        assert response.json() == {'challenge': 'event-challenge'}
    assert feishu_boundary == []


@pytest.mark.parametrize('body', [b'{"event":"fixture"}', b'\xff\x00'])
def test_feishu_signature_uses_encrypt_key_and_original_bytes(monkeypatch, body):
    import hashlib
    from services.feishu_client import FeishuClient
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', 'verification-fixture')
    monkeypatch.setenv('FEISHU_ENCRYPT_KEY', 'encrypt-fixture')
    client = FeishuClient()
    signature = hashlib.sha256(b'123nonceencrypt-fixture' + body).hexdigest()
    assert client.verify_signature('123', 'nonce', body, signature) is True
    wrong_key = hashlib.sha256(b'123nonceverification-fixture' + body).hexdigest()
    assert client.verify_signature('123', 'nonce', body, wrong_key) is False
    assert client.verify_signature('123', 'nonce', body + b'changed', signature) is False
    assert client.verify_signature('123', 'changed', body, signature) is False
    assert client.verify_signature('124', 'nonce', body, signature) is False
    assert client.verify_signature('123', 'nonce', body, 'invalid') is False
    monkeypatch.delenv('FEISHU_ENCRYPT_KEY')
    assert FeishuClient().verify_signature('123', 'nonce', body, signature) is False


@pytest.mark.parametrize('present', range(7))
@pytest.mark.parametrize('verification', [False, True])
def test_configured_bot_requires_every_signature_header_before_dispatch(identity_app, feishu_boundary, monkeypatch, present, verification):
    """Observe dispatch without substituting the real event handling behavior."""
    import hashlib
    from services.bot_handler import BotHandler
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', 'verification-fixture')
    monkeypatch.setenv('FEISHU_ENCRYPT_KEY', 'encrypt-fixture')
    calls = []
    original = BotHandler.handle_event
    def observe(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(BotHandler, 'handle_event', observe)
    event = {'type': 'url_verification', 'challenge': 'not-dispatched'}
    body = json.dumps(event if verification else {'event': event}).encode()
    digest = hashlib.sha256(b'123nonceencrypt-fixture' + body).hexdigest()
    values = [('X-Lark-Request-Timestamp', '123'), ('X-Lark-Request-Nonce', 'nonce'), ('X-Lark-Signature', digest)]
    headers = {'Content-Type': 'application/json'}
    headers.update({name: value for index, (name, value) in enumerate(values) if present & (1 << index)})
    response = identity_app.client.post('/api/v1/bot/feishu', content=body, headers=headers)
    assert response.status_code == 401
    assert calls == []
    assert feishu_boundary == []


@pytest.mark.parametrize('token,expected', [(None, 401), ('wrong', 401), ('verification-fixture', 200)])
@pytest.mark.parametrize('schema', [False, True])
@pytest.mark.parametrize('verification', [False, True])
def test_bot_token_only_authentication_and_url_verification(identity_app, feishu_boundary, monkeypatch, token, expected, schema, verification):
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', 'verification-fixture')
    event = {'type': 'url_verification', 'challenge': 'validated'}
    body = dict(event) if verification else {'event': event}
    if schema:
        body['schema'] = '2.0'
        body['header'] = {'token': token} if token is not None else {}
        body['token'] = 'wrong-top-level-should-not-override-header'
    elif token is not None:
        body['token'] = token
    response = identity_app.client.post('/api/v1/bot/feishu', json=body)
    assert response.status_code == expected
    if expected == 200:
        assert response.json() == {'challenge': 'validated'}
    assert feishu_boundary == []


@pytest.mark.parametrize('header', [None, [], {'token': 'wrong'}, {'token': 'verification-fixture'}])
def test_bot_header_token_priority_without_schema(identity_app, feishu_boundary, monkeypatch, header):
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', 'verification-fixture')
    body = {'type': 'url_verification', 'challenge': 'header-verified',
            'token': 'verification-fixture', 'header': header}
    response = identity_app.client.post('/api/v1/bot/feishu', json=body)
    assert response.status_code == (200 if header == {'token': 'verification-fixture'} else 401)
    assert feishu_boundary == []


@pytest.mark.parametrize('verification_token', ['', 'wrong-token'])
def test_bot_encrypt_key_takes_precedence_over_body_token(identity_app, feishu_boundary, monkeypatch, verification_token):
    import hashlib
    monkeypatch.setenv('FEISHU_ENCRYPT_KEY', 'encrypt-fixture')
    monkeypatch.setenv('FEISHU_VERIFICATION_TOKEN', verification_token)
    body = json.dumps({'type': 'url_verification', 'challenge': 'encrypt-verified', 'token': 'wrong-body-token'}).encode()
    signature = hashlib.sha256(b'123nonceencrypt-fixture' + body).hexdigest()
    headers = {'X-Lark-Request-Timestamp': '123', 'X-Lark-Request-Nonce': 'nonce', 'X-Lark-Signature': signature}
    response = identity_app.client.post('/api/v1/bot/feishu', content=body, headers=headers)
    assert response.status_code == 200 and response.json() == {'challenge': 'encrypt-verified'}
    assert feishu_boundary == []


@pytest.mark.parametrize('chat', ['', 'chat-fixture'])
@pytest.mark.parametrize('failure', [False, True])
def test_bot_configured_event_errors_and_alert_delivery(identity_app, feishu_boundary, monkeypatch, chat, failure):
    import requests
    monkeypatch.setenv('FEISHU_APP_ID', 'fixture-app')
    monkeypatch.setenv('FEISHU_APP_SECRET', 'fixture-secret')
    monkeypatch.setenv('FEISHU_ALERT_CHAT_ID', chat)
    if failure:
        def fail(url, **kwargs):
            feishu_boundary.append((url, kwargs))
            raise requests.ConnectionError('fixture offline')
        monkeypatch.setattr(requests, 'post', fail)
    client = identity_app.client
    assert client.get('/api/v1/bot/config').json()['feishu']['app_id'] == 'fixtur***'
    response = client.post('/api/v1/bot/config/feishu/test')
    assert response.status_code == (503 if failure else 200)
    if not failure:
        assert response.json()['status'] == 'ok'
        for event_chat in ('', chat):
            event = {'event': {'type': 'im.message.receive_v1', 'message': {'msg_type': 'text', 'content': '{', 'chat_id': event_chat}}}
            assert client.post('/api/v1/bot/feishu', json=event).json() == {'status': 'ok'}
    feishu_boundary.clear()
    alerts = [{'labels': {'severity': 'critical', 'alertname': 'A'}, 'annotations': {'summary': 'summary'}}] + [{}] * 6
    response = client.post('/api/v1/bot/feishu/alert', json={'alerts': alerts})
    assert response.json() == {'status': 'received', 'alert_count': 7}
    messages = [kwargs for url, kwargs in feishu_boundary if '/im/v1/messages?' in url]
    assert len(messages) == (5 if chat and not failure else 0)
    if messages:
        assert messages[0]['json']['receive_id'] == chat
        card = json.loads(messages[0]['json']['content'])
        assert card['header']['title']['content'] == '🔴 [FIRING] A'
        assert card['elements'][0]['content'] == 'summary'
        fallback = json.loads(messages[1]['json']['content'])
        assert fallback['header']['title']['content'] == '🟡 [FIRING] Unknown'
    assert client.post('/api/v1/bot/feishu/alert', json={}).json()['alert_count'] == 0


def test_member_filtering_orphaned_duplicate_and_foreign_records(identity_app):
    from models import MemberInvite
    from services import tenant_service as ts
    env = identity_app
    first, second = create_org(env), create_org(env, 'Other')
    env.tenant.add_member(first, MemberInvite(user_id='alice'))
    env.tenant.add_member(second, MemberInvite(user_id='bob'))
    alice_path = next(p for p in ts.MEMBERS_DIR.glob('*.json') if 'alice' in p.name)
    (ts.MEMBERS_DIR / 'duplicate.json').write_bytes(alice_path.read_bytes())
    assert [o['org_id'] for o in env.tenant.get_user_orgs('alice')] == [first]
    assert [m.user_id for m in env.tenant.list_members(first)] == ['alice', 'alice']
    assert env.tenant.get_member(first, 'bob') is None
    env.tenant.delete_org(first)
    assert env.tenant.get_user_orgs('alice')[0]['org_id'] == 'default'


def test_auth_service_lazy_init_and_corrupt_local_record(identity_app, monkeypatch):
    from services import auth_service
    monkeypatch.setattr(auth_service, '_service', None)
    service = auth_service.get_auth_service()
    assert auth_service.get_auth_service() is service
    (auth_service.USERS_DIR / 'corrupt.json').write_text('{', encoding='utf-8')
    monkeypatch.setenv('AUTH_ALLOW_ANONYMOUS', 'true')
    assert service.login_local('admin', '') is not None
    assert service._get_or_create_local_user('fresh').roles == ['viewer']


def test_archive_foreign_project_is_rejected(identity_app):
    """A scoped organization admin must not mutate another organization's project."""
    from models import MemberInvite, ProjectCreate
    env = identity_app
    own, other = create_org(env), create_org(env, 'Other')
    env.tenant.add_member(own, MemberInvite(user_id='alice', role='org_admin'))
    project = env.tenant.create_project(other, ProjectCreate(name='Foreign'), 'admin')
    response = env.client.post(f'/api/v1/orgs/{own}/projects/{project.project_id}/archive', headers=env.headers('alice'))
    assert response.status_code == 404
    assert env.tenant.get_project(project.project_id).is_archived is False


def test_api_key_rate_limit_preserves_route_admin_permission(identity_app, monkeypatch):
    from services.api_key_manager import get_api_key_manager
    from middleware import jwt_middleware as jm
    from models import ApiKeyCreate
    monkeypatch.setattr(jm, '_rate_limit_state', {})
    key = get_api_key_manager().create(ApiKeyCreate(name='limited', scopes=['admin:system'], rate_limit_per_minute=1), created_by='alice')
    headers = {'Authorization': 'Bearer ' + key.full_key}
    first = identity_app.client.get('/api/v1/users', headers=headers)
    assert first.status_code == 403 and first.json()['detail'] == 'Admin only'
    second = identity_app.client.get('/api/v1/users', headers=headers)
    assert second.status_code == 429
    assert len(jm._rate_limit_state[key.key_id]) == 1


def test_expired_rate_window_and_periodic_cleanup(monkeypatch):
    import time
    from middleware import jwt_middleware as jm
    now = time.time()
    monkeypatch.setattr(jm, '_rate_limit_state', {'expired': [now - 61], 'active': [now]})
    monkeypatch.setattr(jm, '_last_cleanup', now - 301)
    jm._cleanup_rate_state()
    assert 'expired' not in jm._rate_limit_state
    assert jm._rate_limit_state['active'] == [now]
    assert jm._check_rate_limit('active', 1) is False
    assert jm._check_rate_limit('new', 1) is True
    assert jm._check_rate_limit('new', 1) is False
    monkeypatch.setattr(jm, '_rate_limit_state', {'rolling': [now - 61]})
    assert jm._check_rate_limit('rolling', 1) is True
    assert len(jm._rate_limit_state['rolling']) == 1
    jm._cleanup_rate_state()
    assert 'rolling' in jm._rate_limit_state


@pytest.mark.parametrize('scopes,path,method,expected', [
    (['read:query'], '/api/v1/query', 'POST', True),
    (['read:query'], '/api/v1/query', 'DELETE', False),
    (['read:query'], '/api/v1/query/unmatched', 'POST', False),
    (['read:catalog', 'read:query'], '/api/v1/query', 'POST', True),
    (['unknown'], '/api/v1/query', 'GET', False),
])
def test_scope_selection_does_not_grant_unrelated_writes(scopes, path, method, expected):
    from middleware.jwt_middleware import _check_scope
    assert _check_scope(scopes, path, method) is expected


def test_signed_jwt_rejects_nonnumeric_expiration_and_unsafe_refresh_secret(identity_app, monkeypatch):
    import time
    import jwt
    from middleware import jwt_middleware as jm
    token = jwt.encode({'sub': 'alice', 'type': 'access', 'iss': 'graphrag-backend', 'exp': str(int(time.time()) + 60)}, jm._secret(), algorithm=jm.JWT_ALGORITHM)
    assert jm.decode_token(token) is None
    monkeypatch.delenv('JWT_SECRET_KEY')
    assert jm.decode_token(token) is None
    with pytest.raises(ValueError, match='JWT'):
        jm.create_refresh_token('alice')


