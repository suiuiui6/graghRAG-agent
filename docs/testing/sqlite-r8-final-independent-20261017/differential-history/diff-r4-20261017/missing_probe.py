import os,json
from pathlib import Path
os.environ['ANONYMIZED_TELEMETRY']='False'
import chromadb
from chromadb.config import Settings
r=Path(__file__).parent
c=chromadb.PersistentClient(path=str(r.parent/'diff-r2-20261017/chroma-db'),settings=Settings(anonymized_telemetry=False)).get_collection('diff-boundary',embedding_function=None)
out={'count':c.count(),'get_ids':c.get()['ids'],'queries':[]}
for j in range(3):
    q=c.query(query_embeddings=[[1.,0.]],n_results=201)
    out['queries'].append({'ids':q['ids'][0],'missing':sorted(set(map(str,range(201)))-set(q['ids'][0]))})
q=c.query(query_embeddings=[[1.,0.]],ids=['9'],n_results=1);out['id9_query']=q['ids'][0]
(r/'missing-probe.json').write_text(json.dumps(out,indent=2));print('count/get',out['count'],len(out['get_ids']),'repeat missing',[len(q['missing']) for q in out['queries']],'id9',out['id9_query'])
