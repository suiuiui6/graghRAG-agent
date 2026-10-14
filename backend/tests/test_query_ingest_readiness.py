"""API glue with real auth/doc graphs/persistence and isolated SDK boundaries."""
import json
from types import SimpleNamespace

import networkx as nx
import pytest
from fastapi import BackgroundTasks
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from tests.test_p0_resource_routes import resource_app


@pytest.fixture
def model_boundary(resource_app, monkeypatch):
    env = resource_app
    state = SimpleNamespace(messages=[AIMessage(content='Scoped answer')], error=None, factories=[], calls=[])
    def invoke(payload, config):
        state.calls.append((payload, config))
        if state.error:
            raise state.error
        return {'messages': state.messages}
    def create_agent(**kwargs):
        state.factories.append(kwargs)
        return SimpleNamespace(invoke=invoke)
    monkeypatch.setenv('LANGEXTRACT_API_KEY', 'offline-provider-boundary')
    monkeypatch.setattr(env.query, 'ChatOpenAI', lambda **kwargs: SimpleNamespace(options=kwargs))
    monkeypatch.setattr(env.query, 'create_agent', create_agent)
    monkeypatch.setattr(env.query, 'tool', tool)
    from errors import register_exception_handlers
    register_exception_handlers(env.client.app)
    return env, state


@pytest.mark.parametrize('mode', ['list', 'dict', 'neighbors', 'invalid_json', 'nontext', 'no_messages', 'plain'])
def test_query_source_extraction_preserves_scope_and_reply_modes(model_boundary, mode):
    env, model = model_boundary
    supported = 'doc_a__n1'
    payloads = {'list': [{'node_id': supported}, 42, {}, {'node_id': 'doc_b__n1'}],
                'dict': {'node_id': supported},
                'neighbors': {'neighbors': [None, {'node_id': supported}, {}]}}
    if mode in payloads:
        model.messages = [AIMessage(content='', tool_calls=[{'name': 'search_kg_by_type', 'args': {}, 'id': 'c'}]),
                          ToolMessage(content=json.dumps(payloads[mode]), tool_call_id='c'),
                          AIMessage(content='Scoped answer')]
    elif mode == 'no_messages':
        model.messages = []
    elif mode == 'plain':
        model.messages = ['Plain response']
    elif mode == 'nontext':
        model.messages = [SimpleNamespace(content={'not': 'text'}), AIMessage(content='Scoped answer')]
    else:
        model.messages = [ToolMessage(content='not JSON', tool_call_id='c'), AIMessage(content='Scoped answer')]
    response = env.client.post('/api/v1/query', json={'query': 'question', 'document_id': 'doc_a'}, headers=env.headers('alice'))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['metadata']['document_ids'] == ['doc_a']
    assert data['answer'] == {'no_messages': 'No answer.', 'plain': 'Plain response'}.get(mode, 'Scoped answer')
    if mode in payloads:
        assert [source['node_id'] for source in data['sources']] == [supported]
        assert data['sources'][0]['properties']['document_id'] == 'doc_a'
        assert data['metadata']['tool_calls'] == 1
    else:
        assert data['sources'] is None
    assert model.calls[0][1]['recursion_limit'] == env.query.LEGACY_QUERY_RECURSION_LIMIT


def test_query_rejects_empty_and_can_omit_sources_and_cap_answer(model_boundary):
    env, model = model_boundary
    response = env.client.post('/api/v1/query', json={'query': '   '}, headers=env.headers())
    assert response.status_code == 400 and model.calls == []
    model.messages = [AIMessage(content='a' * 4100)]
    response = env.client.post('/api/v1/query', json={'query': 'q', 'document_id': 'doc_a', 'options': {'include_sources': False}}, headers=env.headers())
    assert response.status_code == 200
    assert response.json()['answer'] == 'a' * 4000 and response.json()['sources'] is None


@pytest.mark.parametrize('language,fragment', [('en', 'step budget'), ('ch', '步数预算'), ('ja', 'ステップ上限')])
def test_query_recursion_limit_is_localized_and_reported(model_boundary, language, fragment):
    env, model = model_boundary
    model.error = GraphRecursionError('controlled SDK recursion failure')
    response = env.client.post('/api/v1/query', json={'query': 'q', 'document_id': 'doc_a', 'options': {'language': language}}, headers=env.headers())
    assert response.status_code == 200, response.text
    assert fragment in response.json()['answer']
    assert response.json()['metadata']['step_limited'] is True


def test_query_sdk_failure_is_sanitized(model_boundary):
    env, model = model_boundary
    model.error = RuntimeError('private provider diagnostic must not be returned')
    response = env.client.post('/api/v1/query', json={'query': 'q', 'document_id': 'doc_a'}, headers=env.headers())
    assert response.status_code == 503, response.text
    assert 'private provider diagnostic' not in response.text


def test_legacy_tools_empty_graph_lazy_initialization_and_reload(model_boundary, monkeypatch):
    env, model = model_boundary
    q = env.query
    monkeypatch.setattr(q, '_agent', None)
    monkeypatch.setattr(q, 'G_grounded', None)
    first = q._get_agent()
    assert q._get_agent() is first and len(model.factories) == 1
    assert {t.name for t in model.factories[0]['tools']} == {'search_kg_by_type', 'get_entity_neighbors'}
    assert model.factories[0]['model'].options['timeout'] == 120
    q.reload_kg()
    assert q._get_agent() is not first and len(model.factories) == 2
    q._build_agent(None)
    assert len(model.factories[-1]['tools']) == 2
    graph = nx.Graph()
    for node, label, properties in [('a', 'Alice', {'topic': 'budget'}), ('b', 'Bob', {})]:
        graph.add_node(node, label=label, properties=properties, entity_type='person_role')
    graph.add_edge('a', 'b', relation_type='knows')
    search = q._make_search_tool(graph)
    assert search.invoke({'entity_type': 'missing', 'keyword': 'absent'}) == 'No entities found.'
    neighbors = q._make_neighbors_tool(graph)
    assert neighbors.invoke({'node_id': 'absent'}) == 'Entity not found.'
    assert neighbors.invoke({'label_keyword': 'absent'}) == 'Entity not found.'
    for label in ('Alice', 'budget'):
        data = json.loads(neighbors.invoke({'label_keyword': label}))
        assert data['source']['node_id'] == 'a' and data['neighbors'][0]['node_id'] == 'b'


@pytest.fixture
def admission(resource_app, monkeypatch):
    env = resource_app
    import routes.ingest as ingest
    monkeypatch.setattr(ingest, 'UPLOADS_DIR', str(env.base / 'uploads'))
    monkeypatch.setattr(ingest, 'TASKS_STORE_PATH', str(env.base / 'output/tasks.json'))
    monkeypatch.setattr(ingest, '_tasks', {})
    scheduled = []
    monkeypatch.setattr(BackgroundTasks, 'add_task', lambda self, fn, *args, **kwargs: scheduled.append((fn, args, kwargs)))
    env.client.app.include_router(ingest.router, prefix='/api/v1')
    return env, ingest, scheduled


@pytest.mark.parametrize('body,expected', [({}, 400), ({'url': 'missing-local.pdf'}, 400),
                                        ({'url': 'https://example.invalid/report.pdf', 'filename': 'report.pdf'}, 200)])
def test_json_admission_validation_and_durable_queued_identity(admission, body, expected):
    env, route, scheduled = admission
    response = env.client.post('/api/v1/ingest', json=body, headers=env.headers())
    assert response.status_code == expected, response.text
    if expected == 200:
        task = response.json()['task_id']
        saved = route._load_tasks()[task]
        assert saved['owner_id'] == 'admin' and saved['status'] == 'pending'
        assert len(scheduled) == 1 and scheduled[0][1][0] == task
        status = env.client.get(f'/api/v1/status/{task}', headers=env.headers())
        assert status.status_code == 200 and status.json()['duration_seconds'] == 0
    else:
        assert not scheduled


def test_local_admission_and_upload_input_errors(admission, monkeypatch):
    env, route, scheduled = admission
    original = env.base / 'uploads/local.md'
    original.write_bytes(b'local fixture')
    response = env.client.post('/api/v1/ingest', json={'url': str(original), 'filename': 'local.md'}, headers=env.headers())
    assert response.status_code == 200 and response.json()['filename'] == 'local.md'
    assert scheduled[0][1][1] == str(original)
    response = env.client.post('/api/v1/ingest', content='not-json', headers={**env.headers(), 'Content-Type': 'application/json'})
    assert response.status_code == 400
    response = env.client.post('/api/v1/ingest', files={'file': ('unsupported.exe', b'fixture')}, headers=env.headers())
    assert response.status_code == 400
    monkeypatch.setattr(route, 'MAX_FILE_SIZE', 1)
    response = env.client.post('/api/v1/ingest', files={'file': ('large.md', b'too large')}, headers=env.headers())
    assert response.status_code == 400
    assert env.client.get('/api/v1/status/absent', headers=env.headers()).status_code == 404
