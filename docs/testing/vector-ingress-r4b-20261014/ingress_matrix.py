"""Raw 312 + 84 retained oracle differential; no readback used as input."""
import json, sys, time
from pathlib import Path
import lancedb
from generic_filter import StaticProjection
root=Path(__file__).resolve().parent
oracle=json.loads((root/'numeric-oracle.json').read_text())
p=StaticProjection(oracle['rows'])
db=lancedb.connect(root/f'raw-lance-{time.time_ns()}')
table=db.create_table('raw_matrix',data=[p.encode(r,r['vector']) for r in oracle['rows']],schema=p.schema)
report={'cases':[], 'errors':[], 'differences':[], 'raw_payload_checks':[], 'compat_readback_checks':[]}
for group in ['cases','errors']:
    for entry in oracle[group]:
        try: got={'status':'OK','ids':sorted(r['id'] for r in table.search().where(p.compile(entry['where'])).limit(1000).to_list())}
        except Exception as exc: got={'status':'REJECTED','class':type(exc).__name__,'message':str(exc)}
        report[group].append({'where':entry['where'],**got})
        if (got['status'],got.get('ids'))!=(entry['status'],entry.get('ids')): report['differences'].append({'group':group,'where':entry['where'],'expected':entry,'actual':got})
raw={r['id']:json.loads(r['metadata_json']) for r in table.search().limit(1000).to_list()}
assert raw=={r['id']:r['metadata'] for r in oracle['rows']}
compat={r['id']:json.loads(r['compat_metadata_json']) for r in table.search().limit(1000).to_list()}
assert compat==oracle['readback']
for record in oracle['rows']:
    for key,value in record['metadata'].items(): assert type(raw[record['id']][key]) is type(value)
for rid,meta in oracle['readback'].items():
    for key,value in meta.items(): assert type(compat[rid][key]) is type(value)
report['compat_readback_checks'].append('all compat values and scalar types equal real oracle readback')
report['raw_payload_checks'].append('all raw payload values and scalar types retained')
phase=sys.argv[1]
(root/f'{phase}-raw-matrix.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(report['cases']),'errors':len(report['errors']),'differences':len(report['differences'])}))
raise SystemExit(bool(report['differences']))
