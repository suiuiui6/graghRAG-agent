import json,time
from pathlib import Path
import chromadb
from chromadb.config import Settings
root=Path(__file__).resolve().parent
db=chromadb.PersistentClient(path=str(root/f'wide-{time.time_ns()}'),settings=Settings(anonymized_telemetry=False))
c=db.create_collection('wide_integer',embedding_function=None)
c.add(ids=['one'],metadatas=[{'value':1}],embeddings=[[1.,0.,0.]])
report=[]
for value in [2**64-1,2**64,2**128,10**309]:
    for q in [value,-value]:
        for key in ['value','absent']:
            for op in ['$eq','$in']:
                where={key:{op:[q] if op=='$in' else q}}
                try: result={'status':'OK','ids':c.get(where=where)['ids']}
                except Exception as exc: result={'status':'REJECTED','class':type(exc).__name__,'message':str(exc)}
                report.append({'where':where,**result})
(root/'wide-integer-chroma.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(report),'accepted':sum(r['status']=='OK' for r in report)}))
