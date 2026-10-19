import os,json,math
from pathlib import Path
os.environ['ANONYMIZED_TELEMETRY']='False'
import chromadb
from chromadb.config import Settings
r=Path(__file__).parent;c=chromadb.PersistentClient(path=str(r/'batch-db'),settings=Settings(anonymized_telemetry=False));out={}
for batch in [100,1000]:
 for flavor in ['same','near']:
    v=[[1.,0.]]*201 if flavor=='same' else [[.1235+(i-100)*1e-10,math.sqrt(1-(.1235+(i-100)*1e-10)**2)] for i in range(201)]
    name=f'{flavor}-{batch}';x=c.create_collection(name,embedding_function=None,configuration={'hnsw':{'space':'cosine','batch_size':batch}})
    x.add(ids=list(map(str,range(201))),embeddings=v)
    out[name]={'config':x.configuration,'count':x.count(),'n':[len(x.query(query_embeddings=[[1.,0.]],n_results=201)['ids'][0]) for _ in range(3)]}
(r/'batch.json').write_text(json.dumps(out,indent=2));print(out)
