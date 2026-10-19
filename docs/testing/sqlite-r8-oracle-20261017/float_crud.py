import os,json,math
from pathlib import Path
os.environ.update(PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')
import chromadb
from chromadb.config import Settings
r=Path(__file__).resolve().parent
client=chromadb.PersistentClient(path=str(r/'float-db'),settings=Settings(anonymized_telemetry=False))
out={}
def run(name,fn):
    try:out[name]={'ok':True,'result':fn()}
    except Exception as e:out[name]={'ok':False,'type':type(e).__name__,'message':str(e)}
for label,v in [('ordinary',0.12349999),('round_edge',0.12350001),('large',1e40),('tiny',1e-50)]:
    c=client.create_collection('float-'+label,embedding_function=None,metadata={'hnsw:space':'cosine'})
    run(label+'_add',lambda:c.add(ids=['x'],embeddings=[[v,1.]],documents=['doc'],metadatas=[{'fresh':True,'n':2**63,'entity_ids':'["x"]'}]))
    run(label+'_get',lambda:c.get())
    def query(c=c):
        q=c.query(query_embeddings=[[1.,0.]],n_results=1)
        d=q['distances'][0]
        return {'query':q,'project_score':[round(1-x/2,4) for x in d], 'binary64_reference_score':round((1+v/math.hypot(v,1.))/2,4)}
    run(label+'_query',query)
    run(label+'_large_query',lambda:c.query(query_embeddings=[[1e40,1.]],n_results=1))
    run(label+'_delete_where',lambda:c.delete(where={'fresh':True}))
    run(label+'_after_delete',lambda:{'count':c.count(),'get':c.get()})
    run(label+'_readd',lambda:c.add(ids=['x'],embeddings=[[1.,0.]],documents=['new'],metadatas=[{'new_key':'now'}]))
    run(label+'_new_key_query',lambda:c.get(where={'new_key':'now'}))
(r/'float-crud.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
