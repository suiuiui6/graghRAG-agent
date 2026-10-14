import hashlib
import json
import pathlib
import time
import chromadb
from chromadb.config import Settings

root=pathlib.Path(__file__).resolve().parent
fixture=root/'fixtures.json'
payload=json.loads(fixture.read_text(encoding='utf-8'))
db=chromadb.PersistentClient(path=str(root/f'chroma-{time.time_ns()}'),settings=Settings(anonymized_telemetry=False))
table=db.create_collection('synthetic_truth_r2',embedding_function=None)
table.add(ids=[r['id'] for r in payload['rows']],metadatas=[{k:v for k,v in r.items() if k!='id'} for r in payload['rows']],embeddings=[[1.,0.,0.]]*len(payload['rows']))
cases=[]
for where in payload['cases']:
    try: result={'status':'OK','ids':sorted(table.get(where=where)['ids'])}
    except Exception as exc: result={'status':'REJECTED','error':type(exc).__name__+': '+str(exc)[:500]}
    cases.append({'where':where,**result})
report={'version':chromadb.__version__,'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cases':cases}
out=root/f'chroma-truth-{time.time_ns()}.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
