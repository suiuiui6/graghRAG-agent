import os,json,platform,sys
from pathlib import Path
os.environ.update(PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')
import chromadb
from chromadb.config import Settings
r=Path(__file__).resolve().parent
c=chromadb.PersistentClient(path=str(r/'scale-db'),settings=Settings(anonymized_telemetry=False)).create_collection('scale-case',embedding_function=None,metadata={'hnsw:space':'cosine'})
for start in range(0,11000,5000):
    count=min(5000,11000-start)
    c.add(ids=[f'row-{i}' for i in range(start,start+count)],embeddings=[[1.,0.]]*count,metadatas=[{'group':1}]*count)
q=c.query(query_embeddings=[[1.,0.]],n_results=1001)
page=c.get(limit=1001,offset=10000)
c.add(ids=['wide'],embeddings=[[0.,1.]],documents=['x'*(1024*1024+1)],metadatas=[{'group':2}])
out={'python':platform.python_version(),'chromadb':chromadb.__version__,'count':c.count(),'topk_requested':1001,'topk_returned':len(q['ids'][0]),'page_offset':10000,'page_returned':len(page['ids']),'wide_document_chars':len(c.get(ids=['wide'])['documents'][0]),'input':'range(11000), dimension2, repeated [1,0], wide ASCII x*(1MiB+1)'}
(r/'scale.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
