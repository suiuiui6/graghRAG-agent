import json,math,sqlite3,time,struct,hashlib
from pathlib import Path
import chromadb
from chromadb.config import Settings
from parser_port import parse
r=Path(__file__).resolve().parent
vals=[float(s) for s in (r/'independent-inputs.txt').read_text().splitlines()[:1200]]
p=r/f'random-db-{time.time_ns()}'
c=chromadb.PersistentClient(path=str(p),settings=Settings(anonymized_telemetry=False)).create_collection('random_ingress',embedding_function=None)
c.add(ids=[str(i) for i in range(len(vals))],embeddings=[[1.,float(i+1),0.] for i in range(len(vals))],metadatas=[{'n':v} for v in vals])
back=c.get(); got=dict(zip(back['ids'],back['metadatas']));con=sqlite3.connect(p/'chroma.sqlite3');logs=con.execute('select id,metadata from embeddings_queue').fetchall();bad=[]
for id_,token in logs:
 actual=got[id_]['n'];raw=vals[int(id_)]; predicted=parse(json.dumps(raw))[1]
 if struct.pack('>d',actual)!=struct.pack('>d',predicted):bad.append({'id':id_,'raw':raw,'log':token,'got':actual,'predicted':predicted})
query=[]
for v in vals[:32]:
 for op,fn in [('$eq',lambda a,b:a==b),('$gt',lambda a,b:a>b),('$lt',lambda a,b:a<b)]:
  q=parse(json.dumps(v))[1];want=sorted(id_ for id_,md in got.items() if fn(md['n'],q));w={'n':{op:v}};g=sorted(c.get(where=w)['ids']);qq=sorted(c.query(query_embeddings=[[1.,1.,0.]],where=w,n_results=1200)['ids'][0]);query.append({'where':w,'get_match':g==want,'query_match':qq==want})
report={'version':chromadb.__version__,'records':len(vals),'readback':back,'logs':logs,'differences':bad,'query_cases':query,'source_inputs_sha256':hashlib.sha256((r/'independent-inputs.txt').read_bytes()).hexdigest()}
(r/'real-random.json').write_text(json.dumps(report,indent=2));print(json.dumps({'records':len(vals),'differences':len(bad),'query_cases':len(query),'query_failed':sum(not x['get_match'] or not x['query_match'] for x in query)}));raise SystemExit(bool(bad) or any(not x['get_match'] or not x['query_match'] for x in query))
