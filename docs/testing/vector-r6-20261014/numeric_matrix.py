"""Stable-literal domain only; retain ingress drift in separate H2 evidence."""
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
mode = sys.argv[1]
lo, hi = -(2**63), 2**63 - 1
values = [lo, lo+1, -2, -1, 0, 1, 2, hi-1, hi, -1.5, 1.5, -1e100, 1e100, False, True]
rows = [{'id': f'n{i:02}', 'metadata': {'number': v, 'float_only': float(v)}, 'vector': [float(i+1), 1., 0.]} for i, v in enumerate(values)]
rows.append({'id': 'missing', 'metadata': {'other': 'x'}, 'vector': [16., 1., 0.]})
ops = ['$eq', '$ne', '$gt', '$gte', '$lt', '$lte']
literals = [lo, lo+1, hi-1, hi, -1.5, 1.5, -1e100, 1e100]
cases = [{key: {op: q}} for key in ['number', 'float_only', 'absent'] for q in literals for op in ops]
cases += [{key: {op: q}} for key in ['number', 'float_only', 'absent'] for q in [[-1e100, 1e100], [-1.5, 1.5], [lo, hi]] for op in ['$in', '$nin']]
payload = {'rows': rows, 'cases': cases}
digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
report = {'fixture': payload, 'fixture_sha256': digest, 'cases': [], 'differences': [], 'checks': []}
if mode == 'chroma':
    import chromadb
    from chromadb.config import Settings
    db = chromadb.PersistentClient(path=str(ROOT / f'matrix-chroma-{time.time_ns()}'), settings=Settings(anonymized_telemetry=False))
    table = db.create_collection('stable_matrix', embedding_function=None)
    table.add(ids=[r['id'] for r in rows], metadatas=[r['metadata'] for r in rows], embeddings=[r['vector'] for r in rows])
    def execute(where): return sorted(table.get(where=where)['ids'])
    report['version'] = chromadb.__version__
    back = table.get()
    report['readback'] = dict(zip(back['ids'], back['metadatas']))
elif mode == 'lance':
    import lancedb
    from generic_filter import StaticProjection
    truth = json.loads((ROOT/'matrix-chroma.json').read_text())
    assert truth['fixture_sha256'] == digest
    p = StaticProjection(rows)
    db = lancedb.connect(ROOT / f'matrix-lance-{time.time_ns()}')
    table = db.create_table('stable_matrix', data=[p.encode(r, r['vector']) for r in rows], schema=p.schema)
    def execute(where): return sorted(r['id'] for r in table.search().where(p.compile(where)).limit(100).to_list())
    report['version'] = lancedb.__version__
    # Validation must precede unknown-key shortcut. Out-of-I64 ints are a declared candidate limit.
    for key in ['number', 'absent']:
        for q in [hi+1, math.inf, -math.inf, math.nan]:
            for op in ops + ['$in', '$nin']:
                where = {key: {op: [q] if op in ('$in', '$nin') else q}}
                try: p.compile(where)
                except ValueError: report['checks'].append({'where': where, 'status': 'REJECTED'})
                else: report['differences'].append({'validation_not_rejected': str(where)})
else: raise ValueError(mode)
for i, where in enumerate(cases):
    try: result = {'status': 'OK', 'ids': execute(where)}
    except Exception as exc: result = {'status': 'REJECTED', 'error': type(exc).__name__ + ': ' + str(exc)}
    report['cases'].append({'where': where, **result})
    if mode == 'lance' and (result['status'], result.get('ids')) != (truth['cases'][i]['status'], truth['cases'][i].get('ids')):
        report['differences'].append({'where': where, 'expected': truth['cases'][i], 'actual': result})
report['status'] = 'PASS' if not report['differences'] else 'FAIL'
(ROOT/f'matrix-{mode}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'cases': len(cases), 'differences': len(report['differences']), 'checks': len(report['checks'])}))
raise SystemExit(bool(report['differences']))

