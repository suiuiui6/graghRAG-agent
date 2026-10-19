"""New seeded raw-record / bit / get+query differential; synthetic only."""
import hashlib,json,random,struct,sys,tempfile
from pathlib import Path
r=Path(__file__).resolve().parent
mode=sys.argv[1];rng=random.Random(2026101559)
values=[-(2**63),2**63-1,2**63,-2**63-1,2**64,-2**64,0,-0.0]
values += [sign*((1<<power)+rng.randrange(1,8193)) for power in (63,64,65,80,100,200,500,900,1023) for sign in (-1,1) for _ in range(2)]
values += [10**100,-10**100,10**308,-10**308]
rows=[{'id':f'w{i:03}', 'metadata':{'n':v,'group':i%3},'vector':[float(i+1),1.,0.]} for i,v in enumerate(values)]
queries=[float(v) for v in values[::4]]+[-1,0,1,2**63-1,2**63,2**64,-2**63-1]
cases=[{'n':{op:v}} for v in queries for op in ('$eq','$ne','$lt','$lte','$gt','$gte')]
cases += [{'n':{op:seq}} for op in ('$in','$nin') for seq in ([0,1], [2**63,0],[float(2**63),-1.0],[-1.0,float(2**63)],[10**100,0],[0,10**100])]
payload={'seed':2026101559,'rows':rows,'cases':cases}
digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
def scalar(v):return {'type':type(v).__name__,'bits':struct.pack('>d',v).hex()} if type(v) is float else {'type':type(v).__name__,'value':v}
report={'fixture_sha256':digest,'fixture':payload,'mode':mode,'cases':[],'differences':[]}
if mode=='chroma':
 import chromadb
 from chromadb.config import Settings
 db=chromadb.PersistentClient(path=tempfile.mkdtemp(prefix='fresh-record-chroma-',dir=r),settings=Settings(anonymized_telemetry=False))
 table=db.create_collection('fresh_record_bits',embedding_function=None)
 table.add(ids=[x['id'] for x in rows],metadatas=[x['metadata'] for x in rows],embeddings=[x['vector'] for x in rows])
 result=table.get();report['readback']={k:{field:scalar(v) for field,v in meta.items()} for k,meta in zip(result['ids'],result['metadatas'])}
 def execute(where):
  ids=sorted(table.get(where=where)['ids']);query=sorted(table.query(query_embeddings=[[1.,0.,0.]],where=where,n_results=len(rows))['ids'][0]);assert ids==query
  return ids
 report['version']=chromadb.__version__
elif mode=='lance':
 import lancedb
 from generic_filter import StaticProjection
 truth=json.loads((r/'fresh-wide-record-chroma.json').read_text());assert truth['fixture_sha256']==digest
 p=StaticProjection(rows);db=lancedb.connect(tempfile.mkdtemp(prefix='fresh-record-lance-',dir=r));table=db.create_table('fresh_record_bits',data=[p.encode(x,x['vector']) for x in rows],schema=p.schema)
 stored=table.search().limit(1000).to_list();report['readback']={x['id']:{field:scalar(v) for field,v in json.loads(x['compat_metadata_json']).items()} for x in stored}
 for item in stored:
  raw=json.loads(item['metadata_json']);original=rows[int(item['id'][1:])]['metadata']
  assert {k:scalar(v) for k,v in raw.items()}=={k:scalar(v) for k,v in original.items()}
  compat=json.loads(item['compat_metadata_json'])
  for key,v in compat.items():
   prefix=p.mapping[key];assert item[prefix+'_type']==('float' if type(v) is float else 'int')
   assert scalar(item[prefix+('_float' if type(v) is float else '_int')])==scalar(v)
 if report['readback']!=truth['readback']:report['differences'].append({'readback':'type/bit mismatch','expected':truth['readback'],'actual':report['readback']})
 def execute(where):
  expr=p.compile(where);ids=sorted(x['id'] for x in table.search().where(expr).limit(1000).to_list());query=sorted(x['id'] for x in table.search([1.,0.,0.]).distance_type('cosine').where(expr,prefilter=True).limit(len(rows)).to_list());assert ids==query
  return ids
 report['version']=lancedb.__version__
else:raise ValueError(mode)
for i,where in enumerate(cases):
 try:got={'status':'OK','ids':execute(where)}
 except Exception as exc:got={'status':'REJECTED','class':type(exc).__name__}
 report['cases'].append({'where':where,**got})
 if mode=='lance':
  expected=truth['cases'][i]
  if (got['status'],got.get('ids'))!=(expected['status'],expected.get('ids')):report['differences'].append({'where':where,'expected':expected,'actual':got})
report['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(r/f'fresh-wide-record-{mode}.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'rows':len(rows),'cases':len(cases),'get_query_checks':len(cases),'differences':len(report['differences'])}))
raise SystemExit(bool(report['differences']))
