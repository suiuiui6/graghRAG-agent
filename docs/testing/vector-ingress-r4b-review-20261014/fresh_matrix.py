"""Independent seed 202610141731 new raw finite values; real dependency differential."""
import json,math,random,struct,sys,time,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
rng=random.Random(202610141731)
values=[]
while len(values)<128:
    value=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
    if math.isfinite(value): values.append(value)
rows=[{'id':f'new{i:03}','metadata':{'value':v},'vector':[float(i+1),1.,0.]} for i,v in enumerate(values)]
rows += [{'id':f'special{i}','metadata':{'value':v},'vector':[140.+i,1.,0.]} for i,v in enumerate([-0.0,0.0,math.ulp(0.0),-math.ulp(0.0),sys.float_info.max,-sys.float_info.max])]
rows += [{'id':'i64min','metadata':{'value':-(2**63)},'vector':[130.,1.,0.]}, {'id':'missing','metadata':{'other':True},'vector':[131.,1.,0.]}]
cases=[{'value':{op:v}} for v in values[::8] for op in ['$eq','$ne','$gt','$gte','$lt','$lte']]
cases += [{'value':{op:values[i:i+3]}} for i in range(0,32,4) for op in ['$in','$nin']]
cases += [{key:{op:[-(2**63)-1, -(2**63)]}} for key in ['value','absent'] for op in ['$in','$nin']]
cases += [{key:{op:literal}} for key in ['value','absent'] for op in ['$in','$nin'] for literal in [[-(2**63),-(2**63)-1],[-(2**63)-1,2**63],[2**63,-(2**63)-1]]]
payload={'rows':rows,'cases':cases}
report={'fixture':payload,'fixture_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),'cases':[],'differences':[]}
mode=sys.argv[1]
if mode=='chroma':
    import chromadb
    from chromadb.config import Settings
    db=chromadb.PersistentClient(path=str(root/f'fresh-chroma-{time.time_ns()}'),settings=Settings(anonymized_telemetry=False))
    table=db.create_collection('fresh_ingress',embedding_function=None)
    table.add(ids=[r['id'] for r in rows],metadatas=[r['metadata'] for r in rows],embeddings=[r['vector'] for r in rows])
    back=table.get(); report['readback']=dict(zip(back['ids'],back['metadatas']))
    def execute(where): return sorted(table.get(where=where)['ids'])
else:
    import lancedb
    from generic_filter import StaticProjection
    truth=json.loads((root/'fresh-chroma.json').read_text())
    assert truth['fixture_sha256']==report['fixture_sha256']
    p=StaticProjection(rows)
    db=lancedb.connect(root/f'fresh-lance-{time.time_ns()}')
    table=db.create_table('fresh_ingress',data=[p.encode(r,r['vector']) for r in rows],schema=p.schema)
    stored=table.search().limit(1000).to_list()
    raw={r['id']:json.loads(r['metadata_json']) for r in stored}
    compat={r['id']:json.loads(r['compat_metadata_json']) for r in stored}
    assert raw=={r['id']:r['metadata'] for r in rows}
    assert compat==truth['readback']
    for record in rows:
        for key,v in record['metadata'].items():
            assert type(raw[record['id']][key]) is type(v)
            if type(v) is float: assert struct.pack('>d',raw[record['id']][key])==struct.pack('>d',v)
    for rid,meta in truth['readback'].items():
        for key,v in meta.items():
            assert type(compat[rid][key]) is type(v)
            if type(v) is float: assert struct.pack('>d',compat[rid][key])==struct.pack('>d',v),(rid,v,compat[rid][key])
    report['raw_payload_verified']=True; report['compat_readback_verified']=True
    def execute(where): return sorted(r['id'] for r in table.search().where(p.compile(where)).limit(1000).to_list())
for index,where in enumerate(cases):
    try: result={'status':'OK','ids':execute(where)}
    except Exception as exc: result={'status':'REJECTED','class':type(exc).__name__,'message':str(exc)}
    report['cases'].append({'where':where,**result})
    if mode=='lance' and (result['status'],result.get('ids'))!=(truth['cases'][index]['status'],truth['cases'][index].get('ids')): report['differences'].append({'where':where,'expected':truth['cases'][index],'actual':result})
(root/f'fresh-{mode}.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(cases),'differences':len(report['differences'])}))
raise SystemExit(bool(report['differences']))

