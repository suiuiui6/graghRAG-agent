"""Wide integer generic JSON ingress, success IDs and rejection states separately."""
import json,sys,time,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
mode=sys.argv[1]
phase=sys.argv[2] if len(sys.argv)>2 else 'green'
rows=[{'id':f'r{i}','metadata':{'value':v},'vector':[float(i+1),1.,0.]} for i,v in enumerate([-(2**63),-1,0,1,2**63-1,-1e100,1e100,False])]
rows.append({'id':'missing','metadata':{'other':True},'vector':[9.,1.,0.]})
values=[2**64-1,2**64,2**128,10**309]
cases=[{key:{op:q}} for key in ['value','absent'] for v in values for q in [v,-v] for op in ['$eq','$ne','$gt','$gte','$lt','$lte']]
lists=[[v,-v] for v in values]+[[-v,v] for v in values]+[[-(2**63)-1,2**64],[2**64,-(2**63)-1],[-(2**63),-(2**63)-1],[-(2**63)-1,-(2**63)]]
cases += [{key:{op:q}} for key in ['value','absent'] for q in lists for op in ['$in','$nin']]
old=json.loads((root/'wide-integer-chroma.json').read_text())
payload={'rows':rows,'cases':cases}
report={'fixture':payload,'fixture_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),'cases':[],'differences':[],'old32':[],'old32_differences':[]}
if mode=='chroma':
    import chromadb
    from chromadb.config import Settings
    db=chromadb.PersistentClient(path=str(root/f'wide-matrix-chroma-{time.time_ns()}'),settings=Settings(anonymized_telemetry=False))
    table=db.create_collection('wide_matrix',embedding_function=None)
    table.add(ids=[r['id'] for r in rows],metadatas=[r['metadata'] for r in rows],embeddings=[r['vector'] for r in rows])
    def execute(where): return sorted(table.get(where=where)['ids'])
else:
    import lancedb
    from generic_filter import StaticProjection
    truth=json.loads((root/'wide-matrix-chroma.json').read_text())
    assert truth['fixture_sha256']==report['fixture_sha256']
    p=StaticProjection(rows)
    db=lancedb.connect(root/f'wide-matrix-lance-{time.time_ns()}')
    table=db.create_table('wide_matrix',data=[p.encode(r,r['vector']) for r in rows],schema=p.schema)
    def execute(where): return sorted(r['id'] for r in table.search().where(p.compile(where)).limit(1000).to_list())
    # Original 32 fixture was a single integer record, so reproduce it independently.
    p32=StaticProjection([{'id':'one','metadata':{'value':1}}])
    t32=db.create_table('old32',data=[p32.encode({'id':'one','metadata':{'value':1}})],schema=p32.schema)
    for entry in old:
        try: got={'status':'OK','ids':sorted(r['id'] for r in t32.search().where(p32.compile(entry['where'])).limit(1000).to_list())}
        except Exception as exc: got={'status':'REJECTED','class':type(exc).__name__,'message':str(exc)}
        report['old32'].append({'where':entry['where'],**got})
        if (got['status'],got.get('ids'))!=(entry['status'],entry.get('ids')): report['old32_differences'].append({'expected':entry,'actual':got})
for index,where in enumerate(cases):
    try: got={'status':'OK','ids':execute(where)}
    except Exception as exc: got={'status':'REJECTED','class':type(exc).__name__,'message':str(exc)}
    report['cases'].append({'where':where,**got})
    if mode=='lance' and (got['status'],got.get('ids'))!=(truth['cases'][index]['status'],truth['cases'][index].get('ids')): report['differences'].append({'expected':truth['cases'][index],'actual':got})
(root/f'{phase}-wide-matrix-{mode}.json').write_text(json.dumps(report,indent=2))
if mode=='chroma': (root/'wide-matrix-chroma.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(cases),'differences':len(report['differences']),'old32_differences':len(report['old32_differences'])}))
raise SystemExit(bool(report['differences'] or report['old32_differences']))
