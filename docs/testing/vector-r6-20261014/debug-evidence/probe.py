import hashlib, json, math, pathlib, sqlite3, sys, time
import chromadb
from chromadb.config import Settings
r=pathlib.Path(__file__).resolve().parent
db=r/('synthetic-'+str(time.time_ns()))
c=chromadb.PersistentClient(path=str(db),settings=Settings(anonymized_telemetry=False)).create_collection('r6_numeric_debug',embedding_function=None,metadata={'hnsw:space':'cosine'})
values=[-(2**63),2**63-1,2**63,2**64,-2**63-1,2**63+1025,-2**63-1025,10**100,10**308,10**309,10**400]
out=[]
for i,v in enumerate(values):
 row={'input':str(v)}
 try:
  ident='v'+str(i);c.add(ids=[ident],embeddings=[[1.,0.,0.]],metadatas=[{'n':v}]);got=c.get(ids=[ident])['metadatas'][0]['n'];row.update(status='accepted',type=type(got).__name__,readback=str(got),hex=got.hex() if type(got) is float else None)
 except Exception as e:row.update(status='rejected',exception=type(e).__name__,message=str(e))
 out.append(row)
vectors=[]
for name,v in [('finite',[1.,0.,0.]),('nan',[float('nan'),0.,0.]),('posinf',[float('inf'),0.,0.]),('neginf',[-float('inf'),0.,0.])]:
 try:
  got=c.query(query_embeddings=[v],n_results=3);vectors.append({'name':name,'status':'accepted','ids':got['ids'],'distances':got['distances']})
 except Exception as e:vectors.append({'name':name,'status':'rejected','exception':type(e).__name__,'message':str(e)})
con=sqlite3.connect(db/'chroma.sqlite3');log=con.execute('select id,metadata from embeddings_queue').fetchall()
(r/'result.json').write_text(json.dumps({'version':chromadb.__version__,'python':sys.version,'records':out,'queries':vectors,'queue':log,'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},indent=2),encoding='utf8')
assert all(x['status']=='accepted' for x in out[:9])
assert all(x['status']=='rejected' for x in out[9:])
print('11 metadata boundaries and 4 vector observations captured')
