import os, sys, json, hashlib, datetime, platform
from pathlib import Path
os.environ.update(PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')
import chromadb
from chromadb.config import Settings
root=Path(__file__).resolve().parent
client=chromadb.PersistentClient(path=str(root/'synthetic-db'),settings=Settings(anonymized_telemetry=False))
out={'python':platform.python_version(),'chromadb':chromadb.__version__,'executable':sys.executable,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':{}}
def check(name, fn):
    try: out['cases'][name]={'ok':True,'result':fn()}
    except Exception as e: out['cases'][name]={'ok':False,'type':type(e).__name__,'message':str(e)}
def new(name,dim=512):
    return client.create_collection(name=name,embedding_function=None,metadata={'hnsw:space':'cosine','dimension':dim})
c=new('r8-base')
c.add(ids=['z','a','m'],embeddings=[[1.,0.],[0.,1.],[-1.,0.]],documents=['Z','A','M'],metadatas=[{'n':1},{'n':2},{'n':3}])
for name,fn in {
 'get_all':lambda:c.get(), 'get_requested_order':lambda:c.get(ids=['m','z','a']),
 'get_repeated':lambda:c.get(ids=['z','z']), 'get_empty_ids':lambda:c.get(ids=[]),
 'get_missing':lambda:c.get(ids=['absent','a']), 'empty_where':lambda:c.get(where={}),
 'get_page':lambda:c.get(limit=1,offset=1),
 'get_limit_zero':lambda:c.get(limit=0), 'get_negative_offset':lambda:c.get(offset=-1),
 'duplicate_batch':lambda:c.add(ids=['b','b'],embeddings=[[1.,0.],[0.,1.]]),
 'duplicate_existing':lambda:c.add(ids=['z'],embeddings=[[0.,1.]],documents=['REPLACEMENT']),
 'after_duplicate':lambda:c.get(ids=['z']),
 'dimension_mismatch':lambda:c.add(ids=['bad'],embeddings=[[1.,0.,0.]]),
}.items():check(name,fn)
for k in [-1,0,1,3,4,1001]:check('topk_'+str(k),lambda k=k:c.query(query_embeddings=[[1.,0.]],n_results=k))
zero=new('r8-zero',2)
check('zero_add',lambda:zero.add(ids=['zero','unit'],embeddings=[[0.,0.],[1.,0.]],documents=['zero','unit']))
check('zero_query',lambda:zero.query(query_embeddings=[[0.,0.]],n_results=2))
check('unit_query_with_zero',lambda:zero.query(query_embeddings=[[1.,0.]],n_results=2))
empty=new('r8-empty',3)
check('empty_query',lambda:empty.query(query_embeddings=[[1.,0.]],n_results=1))
check('first_add_ignores_declared_dimension',lambda:empty.add(ids=['one'],embeddings=[[1.,0.]]))
check('query_wrong_dimension',lambda:empty.query(query_embeddings=[[1.,0.,0.]],n_results=1))
for dim in [0,1,4097]:
    dc=new('r8-dim-'+str(dim),dim)
    check('actual_dim_'+str(dim),lambda dc=dc,dim=dim:dc.add(ids=['x'],embeddings=[[1.]*dim]))
check('max_batch_size',lambda:client.get_max_batch_size())
check('more_than_1000_add',lambda:c.add(ids=['large-'+str(i) for i in range(1001)],embeddings=[[1.,0.]]*1001))
check('count_after_large_batch',lambda:c.count())
out['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
out['input_policy']='fixed synthetic literals and range(1001), no production data or provider'
(root/'oracle.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
