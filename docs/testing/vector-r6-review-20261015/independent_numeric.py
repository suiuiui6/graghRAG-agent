import hashlib,json,pathlib,random,struct,sys,tempfile
out=pathlib.Path(__file__).resolve().parent;root=pathlib.Path(sys.argv[1]).resolve();mode=sys.argv[2]
sys.path.insert(0,str(root));rng=random.Random(84015619)
values=[-2**63,2**63-1,2**63,-2**63-1,2**64-1,-2**64,0,-0.0]
for power in (63,64,70,95,127,255,511,767,1000,1020):
 for sign in (-1,1):values.append(sign*((1<<power)+rng.randrange(1,1<<max(14,power-48))))
values.extend([int(sys.float_info.max),-int(sys.float_info.max),10**307,-10**307])
rows=[{'id':f'i{i:03}','metadata':{'n':v,'bucket':i%2}} for i,v in enumerate(values)]
queries=[float(values[i]) for i in (2,3,4,10,17,23,29)]+[-1,0,1,2**63,-2**63-1,10**400]
cases=[{'n':{op:v}} for v in queries for op in ('$eq','$ne','$gt','$gte','$lt','$lte')]
cases.extend({'n':{op:v}} for op in ('$in','$nin') for v in ([0,1],[2**63,0],[float(2**63),0.0],[-float(2**63),1.0],[10**100,0],[0,10**100]))
fixture={'seed':84015619,'rows':rows,'cases':cases};digest=hashlib.sha256(json.dumps(fixture,sort_keys=True).encode()).hexdigest()
def scalar(v):return {'type':type(v).__name__,'bits':struct.pack('>d',v).hex()} if type(v) is float else {'type':type(v).__name__,'value':v}
report={'fixture':fixture,'fixture_sha256':digest,'mode':mode,'cases':[],'differences':[]}
if mode=='chroma':
 import chromadb
 from chromadb.config import Settings
 db=chromadb.PersistentClient(path=tempfile.mkdtemp(prefix='numeric-chroma-',dir=out),settings=Settings(anonymized_telemetry=False))
 table=db.create_collection('review_numeric',embedding_function=None)
 table.add(ids=[r['id'] for r in rows],metadatas=[r['metadata'] for r in rows],embeddings=[[1.,0.,0.]]*len(rows))
 read=table.get();report['readback']={k:{n:scalar(v) for n,v in m.items()} for k,m in zip(read['ids'],read['metadatas'])}
 def execute(where):
  a=sorted(table.get(where=where)['ids']);b=sorted(table.query(query_embeddings=[[1.,0.,0.]],n_results=len(rows),where=where)['ids'][0]);assert a==b;return a
else:
 import lancedb
 from generic_filter import StaticProjection
 from vector_errors import VectorInputError
 truth=json.loads((out/'independent-numeric-chroma.json').read_text());assert truth['fixture_sha256']==digest
 p=StaticProjection(rows);db=lancedb.connect(tempfile.mkdtemp(prefix='numeric-lance-',dir=out));table=db.create_table('review_numeric',data=[p.encode(r) for r in rows],schema=p.schema)
 read=table.search().limit(1000).to_list();report['readback']={r['id']:{n:scalar(v) for n,v in json.loads(r['compat_metadata_json']).items()} for r in read}
 for r in read:
  raw=json.loads(r['metadata_json']);original=rows[int(r['id'][1:])]['metadata'];assert {n:scalar(v) for n,v in raw.items()}=={n:scalar(v) for n,v in original.items()}
  for n,v in json.loads(r['compat_metadata_json']).items():
   prefix=p.mapping[n];tag='float' if type(v) is float else 'int';assert r[prefix+'_type']==tag and scalar(r[prefix+'_'+tag])==scalar(v)
 if truth['readback']!=report['readback']:report['differences'].append('readback type/bits')
 for v in (10**400,-10**401):
  try:StaticProjection([{'id':'overflow','metadata':{'n':v}}])
  except VectorInputError as e:assert e.code=='invalid_input' and e.__cause__ is not None
  else:raise AssertionError('true overflow accepted')
 def execute(where):
  expr=p.compile(where);a=sorted(r['id'] for r in table.search().where(expr).limit(1000).to_list());b=sorted(r['id'] for r in table.search([1.,0.,0.]).distance_type('cosine').where(expr,prefilter=True).limit(len(rows)).to_list());assert a==b;return a
for i,where in enumerate(cases):
 try:result={'status':'OK','ids':execute(where)}
 except Exception as e:result={'status':'REJECTED','class':type(e).__name__}
 report['cases'].append(result)
 if mode=='lance' and (result['status'],result.get('ids'))!=(truth['cases'][i]['status'],truth['cases'][i].get('ids')):report['differences'].append({'case':i,'where':where,'actual':result,'expected':truth['cases'][i]})
report['script_sha256']=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
(out/f'independent-numeric-{mode}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'cases':len(cases),'differences':len(report['differences'])}));assert not report['differences']
