"""Bounded synthetic R2 follow-up; no product/provider imports."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
MODE = sys.argv[1]
values = [-(2**63), -(2**63)+1, -2, -1, 0, 2**63-2, 2**63-1]
rows = [{'id': f'boundary-{i}', 'metadata': {'number': v, 'group': 'selected' if i % 2 else 'other'}, 'vector': [float(i+1), 1., 0.]} for i, v in enumerate(values)]
rows += [{'id': 'float-negative', 'metadata': {'number': -1.5, 'group': 'selected'}, 'vector': [8., 1., 0.]}, {'id': 'missing-number', 'metadata': {'group': 'other'}, 'vector': [9., 1., 0.]}]
for i, row in enumerate(rows):
    row['metadata']['float_only'] = float(i)
cases = [{'number': {op: value}} for value in [-(2**63), -(2**63)+1, -1.5, -1, 2**63-2, 2**63-1] for op in ['$eq', '$ne', '$gt', '$gte', '$lt', '$lte']]
cases += [{'number': {'$in': [-2, -1]}}, {'number': {'$nin': [-2, -1]}}, {'group': 'selected'}, {'group': 'absent'}]
cases += [{key: {'$gt': value}} for key in ['number', 'float_only'] for value in [1e100, -1e100]]
payload = {'rows': rows, 'cases': cases}
fixture_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
report = {'mode': MODE, 'fixture_sha256': fixture_hash, 'fixture': payload, 'cases': [], 'differences': [], 'checks': []}

if MODE == 'chroma':
    import chromadb
    from chromadb.config import Settings
    db = chromadb.PersistentClient(path=str(ROOT / f'boundary-chroma-{time.time_ns()}'), settings=Settings(anonymized_telemetry=False))
    table = db.create_collection('boundary_truth', embedding_function=None)
    table.add(ids=[r['id'] for r in rows], metadatas=[r['metadata'] for r in rows], embeddings=[r['vector'] for r in rows])
    def execute(where):
        return sorted(table.get(where=where)['ids'])
    report['version'] = chromadb.__version__
elif MODE == 'lance':
    import lancedb
    import numpy as np
    from generic_filter import StaticProjection
    truth = json.loads((ROOT / 'boundary-chroma.json').read_text(encoding='utf-8'))
    assert truth['fixture_sha256'] == fixture_hash
    projection = StaticProjection(rows)
    dbpath = ROOT / f'boundary-lance-{time.time_ns()}'
    db = lancedb.connect(dbpath)
    table = db.create_table('boundary', data=[projection.encode(r, r['vector']) for r in rows], schema=projection.schema)
    # Fresh connection restores the mapping from persisted schema, without fixture inference.
    reopened = lancedb.connect(dbpath).open_table('boundary')
    restored = StaticProjection.__new__(StaticProjection)
    restored.schema = reopened.schema
    restored.mapping = json.loads(reopened.schema.metadata[b'metadata_projection'])
    assert restored.mapping == projection.mapping
    stored = {r['id']: json.loads(r['metadata_json']) for r in reopened.search().limit(100).to_list()}
    for r in rows:
        actual = stored[r['id']]
        assert set(actual) == set(r['metadata'])
        for key, value in r['metadata'].items():
            assert type(actual[key]) is type(value) and actual[key] == value
    report['checks'] += ['fresh_connection_schema_mapping_restore', 'metadata_exact_values_and_types']
    rejected = []
    deep = {'number': 0}
    for _ in range(18): deep = {'$and': [deep, {'number': 0}]}
    wide = {'$and': [{'number': 0}] * 65}
    nodes = {'$and': [{'$or': [{'number': 0}] * 64} for _ in range(9)]}
    for name, where in [('depth', deep), ('width', wide), ('nodes', nodes), ('list_size', {'number': {'$in': list(range(65))}})]:
        try: restored.compile(where)
        except ValueError: rejected.append(name)
        else: raise AssertionError(f'not rejected: {name}')
    accepted = restored.encode({'id': 'wide-accepted', 'metadata': {'number': 2**63}})
    import struct
    assert type(json.loads(accepted['metadata_json'])['number']) is int
    assert json.loads(accepted['metadata_json'])['number'] == 2**63
    compat = json.loads(accepted['compat_metadata_json'])['number']
    prefix = restored.mapping['number']
    assert type(compat) is float and accepted[prefix+'_type'] == 'float'
    assert struct.pack('>d', compat) == struct.pack('>d', float(2**63)) == struct.pack('>d', accepted[prefix+'_float'])
    report['checks'].append('wide_record_accept_raw_type_compat_projection_bits')
    for name, meta in [('new_key', {'unseen': 1}), ('int_overflow', {'number': 10**400}), ('nonfinite', {'number': float('inf')})]:
        try: restored.encode({'id': 'invalid', 'metadata': meta})
        except ValueError: rejected.append(name)
        else: raise AssertionError(f'not rejected: {name}')
    report['rejected'] = rejected
    def execute(where):
        return sorted(r['id'] for r in reopened.search().where(restored.compile(where)).limit(100).to_list())
    report['vector_checks'] = []
    for where in [{'group': 'selected'}, {'number': {'$lt': -1}}, {'group': 'absent'}]:
        allowed = set(truth['cases'][cases.index(where)]['ids']) if where in cases else set(truth['cases'][cases.index({'number': {'$lt': -1}})]['ids'])
        for k in [1, 3, 20]:
            query = [1., 2., 0.]
            q = np.asarray(query, dtype=np.float64)
            def distance(row):
                vector = np.asarray(row['vector'], dtype=np.float64)
                return float(1 - np.dot(vector, q) / (np.linalg.norm(vector) * np.linalg.norm(q)))
            expected = sorted((distance(r), r['id']) for r in rows if r['id'] in allowed)[:k]
            actual = reopened.search(query).distance_type('cosine').where(restored.compile(where), prefilter=True).limit(k).to_list()
            assert [r['id'] for r in actual] == [ident for _, ident in expected]
            assert np.allclose([r['_distance'] for r in actual], [d for d, _ in expected], rtol=0, atol=2e-7)
            scores = [1 - r['_distance']/2 for r in actual]
            assert np.allclose(scores, [(2-d)/2 for d, _ in expected], rtol=0, atol=1e-7)
            report['vector_checks'].append({'where': where, 'k': k, 'ids': [r['id'] for r in actual], 'distances': [r['_distance'] for r in actual], 'scores': scores, 'reference_distances': [d for d, _ in expected], 'distance_atol': 2e-7, 'score_atol': 1e-7})
    report['version'] = lancedb.__version__
else:
    raise ValueError(MODE)

for index, where in enumerate(cases):
    try: result = {'status': 'OK', 'ids': execute(where)}
    except Exception as exc: result = {'status': 'REJECTED', 'error': type(exc).__name__ + ': ' + str(exc)[:500]}
    report['cases'].append({'where': where, **result})
    if MODE == 'lance':
        expected = truth['cases'][index]
        if (result['status'], result.get('ids')) != (expected['status'], expected.get('ids')):
            report['differences'].append({'where': where, 'expected': expected, 'actual': result})
report['status'] = 'PASS' if not report['differences'] else 'FAIL'
report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(ROOT / f'boundary-{MODE}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'cases': len(cases), 'differences': report['differences']}))
raise SystemExit(0 if not report['differences'] else 1)
