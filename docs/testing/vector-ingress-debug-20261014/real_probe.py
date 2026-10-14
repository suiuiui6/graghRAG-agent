import json,math,sqlite3,time,hashlib
from pathlib import Path
import chromadb
from chromadb.config import Settings
root=Path(__file__).resolve().parent
vals=[math.nextafter(float(-(2**63)),math.inf),math.nextafter(float(2**63),-math.inf),float(-(2**63)),float(2**63),1.2345678901234567]
p=root/f'db-{time.time_ns()}'
c=chromadb.PersistentClient(path=str(p),settings=Settings(anonymized_telemetry=False)).create_collection('ingress_debug',embedding_function=None)
c.add(ids=[str(i) for i in range(len(vals))],embeddings=[[float(i+1),1.,0.] for i in range(len(vals))],metadatas=[{'n':v} for v in vals])
con=sqlite3.connect(p/'chroma.sqlite3')
r={'version':chromadb.__version__,'raw':[{'repr':repr(v),'hex':v.hex()} for v in vals],'readback':c.get(),'tables':[x[0] for x in con.execute("select name from sqlite_master where type='table'")],'log':con.execute('select id,metadata from embeddings_queue').fetchall(),'stored':con.execute('select * from embedding_metadata').fetchall(),'queries':[]}
for v in vals:
 for op in ['$eq','$gt','$lt']:
  w={'n':{op:v}}
  r['queries'].append({'json':json.dumps(w),'get':c.get(where=w)['ids'],'query':c.query(query_embeddings=[[1.,1.,0.]],where=w,n_results=5)['ids']})
(root/'real-probe.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps(r,indent=2))
