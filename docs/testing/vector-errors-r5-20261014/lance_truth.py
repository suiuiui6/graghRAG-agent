from datetime import timedelta
import hashlib
import json
import pathlib
import time
import lancedb
from generic_filter import StaticProjection, NUMERIC_RULES

root=pathlib.Path(__file__).resolve().parent
fixture=root/'fixtures.json'
data=json.loads(fixture.read_text(encoding='utf-8'))
truth=json.loads(sorted(root.glob('chroma-truth-*.json'))[-1].read_text(encoding='utf-8'))
assert truth['fixture_sha256']==hashlib.sha256(fixture.read_bytes()).hexdigest()
records=[{'id':row['id'],'metadata':{k:v for k,v in row.items() if k!='id'}} for row in data['rows']]
projection=StaticProjection(records)
db=lancedb.connect(root/f'lance-{time.time_ns()}',read_consistency_interval=timedelta(0))
table=db.create_table('generic',data=[projection.encode(row) for row in records],schema=projection.schema)
assert json.loads(table.schema.metadata[b'metadata_projection'])==projection.mapping
results=[]
differences=[]
for index,(where,expected) in enumerate(zip(data['cases'],truth['cases'],strict=True)):
    try: got={'status':'OK','ids':sorted(x['id'] for x in table.search().where(projection.compile(where)).limit(100).to_list())}
    except Exception as exc: got={'status':'REJECTED','error':type(exc).__name__+': '+str(exc)[:500]}
    record={'where':where,**got}
    results.append(record)
    if (got['status'],got.get('ids'))!=(expected['status'],expected.get('ids')): differences.append({'index':index,'where':where,'expected':expected,'got':got})
# Exact metadata survives projection; external key never becomes a column identifier.
stored={row['id']:json.loads(row['metadata_json']) for row in table.search().limit(100).to_list()}
assert stored=={row['id']:{k:v for k,v in row.items() if k!='id'} for row in data['rows']}
assert all(name.startswith('m') for name in projection.mapping.values())
reopened=db.open_table('generic')
assert reopened.count_rows()==6 and reopened.schema.metadata==table.schema.metadata
table.delete(projection.compile({'source':'s1'})); assert table.count_rows()==4
table.add([projection.encode(row) for row in records if row['metadata'].get('source')=='s1'])
assert table.count_rows()==6
report={'status':'PASS' if not differences else 'FAIL','version':lancedb.__version__,'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'compiler_sha256':hashlib.sha256((root/'generic_filter.py').read_bytes()).hexdigest(),'mapping':projection.mapping,'numeric_rules':NUMERIC_RULES,'cases':results,'differences':differences,'native_contract_checks':['metadata_roundtrip','mapping_in_table_schema','reopen','generic_source_delete_restore'],'not_run':['complete_VectorStore_adapter','incremental_new_key_backfill','multi_writer_schema_evolution','application_snapshot_barrier','full_unbounded_metadata_contract']}
out=root/f'lance-truth-{time.time_ns()}.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'cases':len(results),'differences':differences,'output':str(out)},ensure_ascii=True))
raise SystemExit(0 if not differences else 1)
