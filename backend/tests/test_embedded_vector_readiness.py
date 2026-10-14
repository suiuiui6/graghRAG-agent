"""Real embedded vector persistence and deployment attack-surface contracts."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))


def test_default_compose_does_not_start_an_unused_chroma_http_server():
    compose = yaml.safe_load((ROOT / 'docker-compose.yml').read_text(encoding='utf-8'))
    assert 'chromadb' not in compose['services']
    backend = compose['services']['backend']
    assert 'chromadb' not in backend.get('depends_on', {})
    assert not any(str(value).startswith(('CHROMADB_HOST=', 'CHROMADB_PORT='))
                   for value in backend.get('environment', []))
    assert 'graphrag_data:/app/output' in backend['volumes']
    assert 'chromadb_data' not in compose['volumes']


def test_ci_uses_the_same_embedded_topology_without_an_external_chroma_server():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8'))
    job = workflow['jobs']['test']
    assert 'chromadb' not in job.get('services', {})
    for step in job['steps']:
        assert 'CHROMADB_HOST' not in step.get('env', {})
        assert 'CHROMADB_PORT' not in step.get('env', {})


def test_vector_adapter_uses_only_embedded_client_and_fixed_collection_metadata():
    tree = ast.parse((BACKEND / 'vector_store.py').read_text(encoding='utf-8'))
    client_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == 'chromadb']
    assert client_calls and {n.func.attr for n in client_calls} == {'PersistentClient'}
    collections = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == 'get_or_create_collection']
    assert len(collections) == 1
    metadata = next(k.value for k in collections[0].keywords if k.arg == 'metadata')
    assert [key.value for key in metadata.keys] == ['hnsw:space', 'dimension']
    assert all(k.arg not in {'embedding_function', 'configuration', 'trust_remote_code'}
               for call in client_calls + collections for k in call.keywords)


def test_real_embedded_store_persists_filters_and_deletes_without_external_embeddings(tmp_path, monkeypatch):
    from doc_processor import Chunk, ChunkMetadata
    from vector_store import VectorStore
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setenv('TRANSFORMERS_OFFLINE', '1')
    monkeypatch.setenv('ANONYMIZED_TELEMETRY', 'FALSE')
    # Old host variables must not redirect the local adapter to a network service.
    monkeypatch.setenv('CHROMADB_HOST', 'no-network.example.invalid')
    monkeypatch.setenv('CHROMADB_PORT', '1')
    store = VectorStore(persist_dir=str(tmp_path / 'vectors'), embedding_dim=2)
    chunks = [Chunk('v1', 'budget record', 'text', metadata=ChunkMetadata('v1', 'a.md', 'md')),
              Chunk('v2', 'other record', 'text', metadata=ChunkMetadata('v2', 'b.md', 'md'))]
    store.add_chunks(chunks, [[1.0, 0.0], [0.0, 1.0]])
    assert store.count() == 2 and store.list_sources() == ['a.md', 'b.md']
    selected = store.search([1.0, 0.0], top_k=1, where={'source_file': 'a.md'})
    assert len(selected) == 1 and selected[0]['chunk_id'] == 'v1' and selected[0]['score'] == 1.0
    assert store._client.get_settings().chroma_api_impl in (
        'chromadb.api.rust.RustBindingsAPI', 'chromadb.api.segment.SegmentAPI')
    # A fresh interpreter proves durable bytes, rather than a shared client cache.
    code = '''import json,sys
sys.path.insert(0,sys.argv[1])
from vector_store import VectorStore
s=VectorStore(persist_dir=sys.argv[2],embedding_dim=2)
print(json.dumps({'count':s.count(),'ids':[r['chunk_id'] for r in s.get_by_ids(['v1','v2'])]}))
'''
    child = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, str(BACKEND), store.persist_dir],
                           capture_output=True, text=True, encoding='utf-8', timeout=45,
                           env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'})
    assert child.returncode == 0, child.stderr
    persisted = json.loads(child.stdout.strip().splitlines()[-1])
    assert persisted['count'] == 2 and set(persisted['ids']) == {'v1', 'v2'}
    store.delete_by_source('a.md')
    assert store.count() == 1 and store.get_by_ids(['v1']) == []
    store.delete_by_chunk_ids(['v2'])
    assert store.count() == 0
