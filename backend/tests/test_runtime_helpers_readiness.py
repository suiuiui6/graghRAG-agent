"""Runtime helper contracts with real local artifacts and provider-only doubles."""
import json
import builtins
import importlib
import os
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest


def test_embedding_batch_cache_merge_corruption_and_model_sharing(tmp_path, monkeypatch):
    import embedding as em
    monkeypatch.setattr(em, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(em, '_st_model_cache', {})
    calls = []
    class LocalModelBoundary:
        def __init__(self, name):
            calls.append(('load', name))
        def encode(self, texts, **kwargs):
            assert kwargs['normalize_embeddings'] is True
            calls.append(('encode', list(texts)))
            return np.array([[float(len(text)), 1.0] for text in texts])
    monkeypatch.setitem(sys.modules, 'sentence_transformers', SimpleNamespace(SentenceTransformer=LocalModelBoundary))
    a = em.EmbeddingClient(model='test/model', batch_size=1)
    b = em.create_embedding_client('test/model')
    assert a.embed_texts([]) == []
    assert a.embed_queries(['pump', 'valve']) == [[4.0, 1.0], [5.0, 1.0]]
    assert a.embed_query('pump') == [4.0, 1.0]
    assert b.embed_text('other') == [5.0, 1.0]
    assert a.st_model is b.st_model
    assert em.EmbeddingClient('test/model').cache_size == 3
    assert calls.count(('load', 'test/model')) == 1
    assert len([c for c in calls if c[0] == 'encode']) == 3
    cache = tmp_path / 'test_model_cache.json'
    cache.write_text('bad', encoding='utf-8')
    c = em.EmbeddingClient('test/model')
    assert c.cache_size == 0
    assert c.embed_text('recovered') == [9.0, 1.0]
    cache.write_text('bad', encoding='utf-8')
    assert c.embed_text('new') == [3.0, 1.0]
    assert json.loads(cache.read_text())[c._cache_key('new')] == [3.0, 1.0]
    c.clear_cache()
    assert c.cache_size == 0 and not cache.exists()
    c.clear_cache()


@pytest.mark.parametrize('cleanup_denied', [False, True])
def test_embedding_windows_replace_failure_keeps_persisted_cache(tmp_path, monkeypatch, cleanup_denied):
    import embedding as em
    monkeypatch.setattr(em, 'CACHE_DIR', str(tmp_path))
    client = em.EmbeddingClient('permission-test')
    client._cache[client._cache_key('pump')] = [1.0, 0.0]
    def denied(*args, **kwargs):
        raise PermissionError('simulated filesystem contention')
    monkeypatch.setattr(em.os, 'replace', denied)
    if cleanup_denied:
        monkeypatch.setattr(em.Path, 'unlink', denied)
    client._save_cache()
    cache = tmp_path / 'permission_test_cache.json'
    assert json.loads(cache.read_text())[client._cache_key('pump')] == [1.0, 0.0]
    assert cache.with_suffix('.json.tmp').exists() is cleanup_denied


def test_embedding_double_checked_model_cache_reuses_concurrent_load(tmp_path, monkeypatch):
    import embedding as em
    monkeypatch.setattr(em, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(em, '_st_model_cache', {})
    waiting = threading.Event()
    release = threading.Event()
    real_lock = threading.Lock()
    class ObservedLock:
        def __enter__(self):
            waiting.set()
            assert release.wait(5), 'loader was never released'
            real_lock.acquire()
        def __exit__(self, *args):
            real_lock.release()
    monkeypatch.setattr(em, '_st_model_cache_lock', ObservedLock())
    client = em.EmbeddingClient('concurrent-model')
    results = []
    errors = []
    def load():
        try:
            results.append(client.st_model)
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=load)
    thread.start()
    try:
        assert waiting.wait(5), 'client did not reach model loading lock'
        loaded = object()
        em._st_model_cache['concurrent-model'] = loaded
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors
    assert results == [loaded] and client.st_model is loaded


def test_embedding_import_uses_default_mirror_when_dotenv_is_absent(monkeypatch):
    import embedding as em
    original = builtins.__import__
    def without_dotenv(name, *args, **kwargs):
        if name == 'dotenv':
            raise ImportError('dotenv not installed')
        return original(name, *args, **kwargs)
    monkeypatch.delenv('HF_ENDPOINT', raising=False)
    monkeypatch.setattr(builtins, '__import__', without_dotenv)
    importlib.reload(em)
    assert os.environ['HF_ENDPOINT'] == 'https://hf-mirror.com'
    monkeypatch.setenv('HF_ENDPOINT', 'https://configured.invalid')
    importlib.reload(em)
    assert os.environ['HF_ENDPOINT'] == 'https://configured.invalid'


@pytest.fixture
def quality_tree(tmp_path, monkeypatch):
    from services import quality as q
    for name, leaf in [('KG_DIR', 'kg'), ('FEEDBACK_DIR', 'feedback'), ('CONVERSATIONS_DIR', 'conversations')]:
        target = tmp_path / leaf
        target.mkdir()
        monkeypatch.setattr(q, name, target)
    monkeypatch.setattr(q, 'DOCS_STORE', tmp_path / 'docs.json')
    return q


def _json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_quality_real_tree_bad_documents_feedback_staleness_and_activity(quality_tree):
    q = quality_tree
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=45)
    node_path = q.KG_DIR / 'doc_valid' / 'nodes.json'
    _json(node_path, {'nodes': [{'grounding_status': 'grounded', 'properties': {'confidence': .8}},
                              {'properties': {'confidence': 'unknown'}}]})
    os.utime(node_path, (old.timestamp(), old.timestamp()))
    (q.KG_DIR / 'doc_missing').mkdir()
    _json(q.KG_DIR / 'doc_broken' / 'nodes.json', ['invalid shape'])
    (q.KG_DIR / 'not_doc').mkdir()
    (q.KG_DIR / 'file.txt').write_text('ignore')
    _json(q.FEEDBACK_DIR / 'positive.json', {'rating': 'positive'})
    _json(q.FEEDBACK_DIR / 'negative.json', {'rating': 'negative', 'query_text': 'bad answer'})
    _json(q.FEEDBACK_DIR / 'empty.json', {'rating': 'negative'})
    (q.FEEDBACK_DIR / 'corrupt.json').write_text('{broken')
    _json(q.DOCS_STORE, [{'indexed_at': old.isoformat()}])
    _json(q.CONVERSATIONS_DIR / 'today.json', {'last_active': now.isoformat()})
    _json(q.CONVERSATIONS_DIR / 'old.json', {'last_active': old.isoformat()})
    (q.CONVERSATIONS_DIR / 'corrupt.json').write_text('broken')
    m = q.QualityMonitor()
    extraction = m._extraction_quality()
    assert extraction == {'grounding_rate': .5, 'confidence_avg': .4, 'extraction_error_rate': 1.0,
                           'total_entities': 2, 'grounded_entities': 1}
    feedback = m._feedback_quality()
    assert feedback['total'] == 3 and feedback['negative'] == 2
    assert feedback['negative_clusters'] == ['bad answer']
    assert m._data_freshness() == {'days_since_last_ingest': 45, 'stale_entities': 2, 'conversation_active_today': 1}
    # Trigger bad stale JSON handling, after proving valid stale counts.
    bad = q.KG_DIR / 'doc_broken' / 'nodes.json'
    os.utime(bad, (old.timestamp(), old.timestamp()))
    assert m._data_freshness()['stale_entities'] == 2
    _json(q.DOCS_STORE, [])
    assert m._data_freshness()['days_since_last_ingest'] == 999
    q.DOCS_STORE.write_text('bad')
    assert m._data_freshness()['days_since_last_ingest'] == 999


def test_quality_flat_legacy_and_broken_metrics_are_nonfatal(quality_tree, monkeypatch):
    q = quality_tree
    m = q.QualityMonitor()
    _json(q.KG_DIR / 'nodes.json', {'nodes': [{'grounding_status': 'grounded'}, {}]})
    assert m._extraction_quality()['grounding_rate'] == .5
    (q.KG_DIR / 'nodes.json').write_text('broken')
    assert m._extraction_quality()['total_entities'] == 0
    monkeypatch.setattr(m, '_m', SimpleNamespace())
    assert m._retrieval_quality() == {'path_covers_avg': 0, 'zero_result_total': 0}
    from services import event_bus
    class UnavailableBus:
        def publish(self, *args, **kwargs):
            raise OSError('event transport unavailable')
    monkeypatch.setattr(event_bus, 'get_event_bus', lambda: UnavailableBus())
    report = m.compute()
    assert len(report.alerts) == 3 and report.overall_score == 0
    monkeypatch.setattr(q, '_monitor', None)
    assert q.get_quality_monitor() is q.get_quality_monitor()


def test_quality_fresh_grounded_positive_data_has_no_alerts_and_real_metrics(quality_tree, monkeypatch):
    from prometheus_client import CollectorRegistry, Counter, Gauge
    q = quality_tree
    registry = CollectorRegistry()
    candidates = Gauge('helper_candidates', 'candidates', ['path'], registry=registry)
    candidates.labels('vector').set(2)
    candidates.labels('bm25').set(0)
    zero = Counter('helper_zero', 'zero', registry=registry)
    zero.inc(3)
    metrics = SimpleNamespace(rag_retrieval_candidates=candidates, rag_zero_result_queries=zero)
    for name in ['rag_grounding_rate', 'rag_positive_feedback_ratio', 'rag_stale_entities',
                 'rag_data_freshness_days', 'rag_quality_score']:
        setattr(metrics, name, Gauge('helper_' + name, name, registry=registry))
    now = datetime.now(timezone.utc)
    _json(q.KG_DIR / 'doc_good' / 'nodes.json', {'nodes': [{'grounding_status': 'grounded'}]})
    _json(q.FEEDBACK_DIR / 'good.json', {'rating': 'positive'})
    _json(q.DOCS_STORE, [{'indexed_at': now.isoformat()}])
    monitor = q.QualityMonitor()
    monkeypatch.setattr(monitor, '_m', metrics)
    report = monitor.compute()
    assert report.alerts == [] and report.overall_score == 84.0
    assert report.retrieval_quality == {'path_covers_avg': 1, 'zero_result_total': 3}
    assert metrics.rag_quality_score._value.get() == report.overall_score
    monkeypatch.setattr(q, 'CONVERSATIONS_DIR', q.CONVERSATIONS_DIR / 'missing')
    assert monitor._active_today() == 0


@pytest.mark.parametrize('status,token,expected', [(200, 'dummy-token', 'ok'), (200, None, 'degraded'), (503, None, 'degraded')])
def test_health_http_status_matrix(tmp_path, monkeypatch, status, token, expected):
    import requests
    from services import health_checker as hc
    calls = []
    def response(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=status, json=lambda: {'tenant_access_token': token})
    monkeypatch.setattr(requests, 'get', response)
    monkeypatch.setattr(requests, 'post', response)
    for key, value in [('LANGEXTRACT_API_KEY', 'dummy'), ('LANGEXTRACT_BASE_URL', 'https://provider.invalid/'),
                       ('MINERU_API_URL', 'https://mineru.invalid/'), ('MINERU_API_KEY', 'dummy'),
                       ('AUTH_PROVIDER', 'oidc'), ('OIDC_ISSUER', 'https://oidc.invalid/'),
                       ('FEISHU_APP_ID', 'dummy'), ('FEISHU_APP_SECRET', 'dummy')]:
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(hc, 'CHROMADB_PATH', tmp_path)
    checker = hc.HealthChecker()
    result = checker.probe_all()
    assert checker.get_status() == result
    assert result['feishu_bot']['status'] == expected
    assert result['deepseek_api']['status'] == ('ok' if status == 200 else 'degraded')
    assert result['mineru_api']['status'] == ('ok' if status < 500 else 'degraded')
    assert result['oauth2_provider']['connected'] is (status == 200)
    assert calls[0][0] == 'https://provider.invalid/v1/models'
    assert calls[1][1]['headers'] == {'Authorization': 'Bearer dummy'}
    assert all(c[1]['timeout'] == 10 for c in calls)
    monkeypatch.delenv('MINERU_API_KEY')
    checker._probe_mineru()
    assert calls[-1][1]['headers'] == {}


def test_health_missing_config_network_errors_and_real_sqlite(tmp_path, monkeypatch):
    import requests
    from services import health_checker as hc
    for key in ['LANGEXTRACT_API_KEY', 'MINERU_API_URL', 'OIDC_ISSUER', 'FEISHU_APP_ID']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('AUTH_PROVIDER', 'oidc')
    checker = hc.HealthChecker()
    assert checker._probe_deepseek()['status'] == 'degraded'
    assert checker._probe_mineru()['status'] == 'degraded'
    assert checker._probe_oauth2()['status'] == 'degraded'
    assert checker._probe_feishu()['status'] == 'ok'
    monkeypatch.setenv('AUTH_PROVIDER', 'local')
    assert checker._probe_oauth2()['status'] == 'ok'
    monkeypatch.setattr(hc, 'CHROMADB_PATH', tmp_path)
    assert checker._probe_chromadb()['status'] == 'degraded'
    db = tmp_path / 'chroma.sqlite3'
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE embedding_metadata (id INTEGER)')
        connection.execute('INSERT INTO embedding_metadata VALUES (1)')
    assert checker._probe_chromadb()['documents'] == 1
    with sqlite3.connect(db) as connection:
        connection.execute('DROP TABLE embedding_metadata')
    assert checker._probe_chromadb()['status'] == 'down'
    def unavailable(*args, **kwargs):
        raise requests.Timeout('x' * 300)
    monkeypatch.setattr(requests, 'get', unavailable)
    monkeypatch.setattr(requests, 'post', unavailable)
    for key in ['LANGEXTRACT_API_KEY', 'MINERU_API_URL', 'OIDC_ISSUER', 'FEISHU_APP_ID']:
        monkeypatch.setenv(key, 'dummy')
    monkeypatch.setenv('AUTH_PROVIDER', 'oidc')
    for probe in [checker._probe_deepseek, checker._probe_mineru, checker._probe_oauth2, checker._probe_feishu]:
        result = probe()
        assert result['status'] == 'down' and len(result['message']) == 200
    monkeypatch.setattr(hc, '_checker', None)
    assert hc.get_health_checker() is hc.get_health_checker()


def test_vector_empty_metadata_migration_and_mirror(tmp_path, monkeypatch):
    import vector_store as vs
    from doc_processor import Chunk, ChunkMetadata
    monkeypatch.setenv('ANONYMIZED_TELEMETRY', 'FALSE')
    store = vs.create_vector_store(persist_dir=str(tmp_path / 'vectors'), embedding_dim=2)
    store.add_chunks([], [])
    with pytest.raises(ValueError, match='Length mismatch'):
        store.add_chunks([Chunk('x', 'pump', 'text')], [])
    assert store.search([1., 0.], top_k=1) == []
    assert store.list_sources() == []
    assert store.get_by_ids([]) == []
    store.delete_by_chunk_ids([])
    store.delete_by_source('absent')
    chunks = [Chunk('plain', 'no metadata', 'text'),
              Chunk('meta', 'pump pressure', 'text', metadata=ChunkMetadata('meta', 'pump.md', 'md', page_idx=2))]
    store.add_chunks(chunks, [[1., 0.], [0., 1.]])
    selected = store.search([0., 1.], top_k=1, text_char_limit=4, metadata_keys=['source_file', 'absent'])
    assert selected[0]['text'] == 'pump' and selected[0]['metadata'] == {'source_file': 'pump.md'}
    assert store.list_sources() == ['pump.md'] and store.get_collection_info()['count'] == 2
    migration = store.create_migration_collection(3)
    assert migration.embedding_dim == 3 and migration.count() == 0
    assert vs._parse_chroma_metadata({}) == {}
    assert vs._parse_chroma_metadata({'entity_ids': '{bad', 'entity_types': []}) == {'entity_ids': [], 'entity_types': []}
    monkeypatch.setattr(vs.tempfile, 'gettempdir', lambda: str(tmp_path / 'mirrors'))
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'data').write_text('durable')
    mirror = vs.Path(vs._prepare_sqlite_safe_mirror(str(source)))
    assert (mirror / 'data').read_text() == 'durable'
    (mirror / 'stale').write_text('stale')
    assert not (vs.Path(vs._prepare_sqlite_safe_mirror(str(source))) / 'stale').exists()
    empty = vs.Path(vs._prepare_sqlite_safe_mirror(str(tmp_path / 'missing')))
    assert empty.is_dir() and list(empty.iterdir()) == []
    monkeypatch.setattr(vs, 'HAS_CHROMADB', False)
    with pytest.raises(ImportError, match='chromadb is required'):
        vs.VectorStore(persist_dir=str(tmp_path / 'no-vendor'))


def test_vector_client_constructor_recovers_to_real_temporary_mirror(tmp_path, monkeypatch):
    import vector_store as vs
    real_client = vs.chromadb.PersistentClient
    attempts = []
    def client_boundary(*args, **kwargs):
        attempts.append(kwargs['path'])
        if len(attempts) == 1:
            raise PermissionError('original sqlite volume locked')
        return real_client(*args, **kwargs)
    monkeypatch.setattr(vs.chromadb, 'PersistentClient', client_boundary)
    monkeypatch.setattr(vs.tempfile, 'gettempdir', lambda: str(tmp_path / 'safe'))
    original = tmp_path / 'locked'
    original.mkdir()
    (original / 'marker').write_text('preserved')
    store = vs.VectorStore(persist_dir=str(original), embedding_dim=2)
    assert len(attempts) == 2 and store.persist_dir != str(original)
    assert (vs.Path(store.persist_dir) / 'marker').read_text() == 'preserved'
    assert store.count() == 0
