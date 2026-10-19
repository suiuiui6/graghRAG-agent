import os,sys,json,random,math,hashlib,subprocess
from pathlib import Path
r=Path(__file__).resolve().parent
if len(sys.argv)==1:
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'candidate').glob('*.py')}
    results=[]
    for mode,exe in [('chroma','.tmp/backend-quality-venv-20261012/Scripts/python.exe'),('sqlite','.tmp/sqlite-numpy-r7-20261015/.venv/Scripts/python.exe')]:
        p=subprocess.run([str(Path(exe).resolve()),'-B',str(Path(__file__).resolve()),mode],capture_output=True,text=True,encoding='utf8')
        (r/(mode+'.log')).write_text(p.stdout+'\n'+p.stderr,encoding='utf8');results.append(p.returncode)
    a=json.loads((r/'chroma.json').read_text());b=json.loads((r/'sqlite.json').read_text())
    diffs={k:{'chroma':a[k],'sqlite':b[k]} for k in a if a[k]!=b[k]}
    (r/'comparison.json').write_text(json.dumps({'exit_codes':results,'manifest':manifest,'after':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'candidate').glob('*.py')},'cases':len(a),'diffs':diffs},indent=2))
    print('cases',len(a),'differences',len(diffs),'exits',results);sys.exit(0)
mode=sys.argv[1]
os.environ.update(PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',ANONYMIZED_TELEMETRY='False')
if mode=='chroma':
    import chromadb
    from chromadb.config import Settings
    client=chromadb.PersistentClient(path=str(r/'chroma-db'),settings=Settings(anonymized_telemetry=False))
    def new(name):return client.create_collection(name,embedding_function=None,metadata={'hnsw:space':'cosine'})
else:
    sys.path.insert(0,str(r/'candidate'))
    from vector_store import VectorStore
    def new(name):return VectorStore(name,str(r/'sqlite-db'))
out={}
def add(c,**kw):return (c if mode=='chroma' else c._collection).add(**kw)
def get(c,w):return sorted((c if mode=='chroma' else c._collection).get(where=w)['ids'])
def scores(c,q):
    if mode=='sqlite':return {x['chunk_id']:x['score'] for x in c.search(q,top_k=10000)}
    v=c.query(query_embeddings=[q],n_results=c.count());return {i:round(1-d/2,4) for i,d in zip(v['ids'][0],v['distances'][0])}
vals=[True,False,0,1,-1,1.5,'1',2**53-1,2**53,2**63-1,-2**63,2**64,1e20,-1e20,1e-300]
c=new('diff-meta')
add(c,ids=[str(i) for i in range(len(vals)+1)],embeddings=[[1.,0.]]*(len(vals)+1),metadatas=[{'x':v} for v in vals]+[{'other':1}])
filters=[]
for op in ['$eq','$ne','$gt','$gte','$lt','$lte','$in','$nin']:
    for v in vals:
        if op in ['$gt','$gte','$lt','$lte'] and type(v) not in (int,float):continue
        filters.append({'x':{op:[v] if op in ['$in','$nin'] else v}})
filters.extend([{'$and':[{'x':{'$gte':0}},{'x':{'$ne':True}}]},{'$or':[{'x':{'$in':[1,2]}},{'other':1}]}])
for i,w in enumerate(filters):
    try:out['where-'+str(i)]=get(c,w)
    except Exception:out['where-'+str(i)]='ERROR'
rng=random.Random(2026101701)
for dim in [3,17,128]:
    c=new('diff-random-'+str(dim));vs=[[rng.uniform(-1,1) for _ in range(dim)] for _ in range(120)]
    add(c,ids=[str(i) for i in range(120)],embeddings=vs)
    for j in range(8):out[f'scores-{dim}-{j}']=scores(c,[rng.uniform(-1,1) for _ in range(dim)])
c=new('diff-boundary');vs=[[v,math.sqrt(1-v*v)] for v in [.1235+i*1e-10 for i in range(-100,101)]]
add(c,ids=[str(i) for i in range(201)],embeddings=vs);out['boundary']=scores(c,[1.,0.])
(r/(mode+'.json')).write_text(json.dumps(out,indent=2))
