import os,json,math
from pathlib import Path
os.environ.update(PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')
import chromadb
from chromadb.config import Settings
r=Path(__file__).resolve().parent
c=chromadb.PersistentClient(path=str(r/'round-db'),settings=Settings(anonymized_telemetry=False)).create_collection('round-case',embedding_function=None,metadata={'hnsw:space':'cosine'})
values=[.1235+i*1e-10 for i in range(-100,101)]
vectors=[[v,math.sqrt(1-v*v)] for v in values]
c.add(ids=[str(i) for i in range(len(values))],embeddings=vectors)
q=c.query(query_embeddings=[[1.,0.]],n_results=len(values))
rows=[]
for identifier,d in zip(q['ids'][0],q['distances'][0]):
    i=int(identifier); ref=round((1+values[i])/2,4);actual=round(1-d/2,4)
    rows.append({'id':identifier,'vector':vectors[i],'distance':d,'actual':actual,'binary64_reference':ref})
out={'total':len(rows),'score_mismatches':[x for x in rows if x['actual']!=x['binary64_reference']],'input':'cosine=.1235+i*1e-10 for i=-100..100; [cos,sqrt(1-cos*cos)]'}
(r/'score-boundary.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('rows',len(rows),'mismatches',len(out['score_mismatches']))
