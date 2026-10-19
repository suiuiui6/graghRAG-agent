import os,sys,json,math,hashlib,random,subprocess
from pathlib import Path
os.environ.update(ANONYMIZED_TELEMETRY='False',PYTHON_DOTENV_DISABLED='1',HF_HUB_OFFLINE='1')
import chromadb,numpy as np
from chromadb.config import Settings
r=Path(__file__).parent
cl=chromadb.PersistentClient(path=str(r/'db'),settings=Settings(anonymized_telemetry=False))
def queries(c):
    out={'count':c.count(),'configuration':c.configuration,'calls':{}}
    data=c.get(include=['embeddings']);out['get_count']=len(data['ids'])
    out['stored_hash']=hashlib.sha256(np.array([v for _,v in sorted(zip(data['ids'],data['embeddings']))],dtype='<f4').tobytes()).hexdigest()
    for k in [1,20,100,200,201,250]:
        for kind,kw in [('none',{}),('oneid',{'ids':['9']}),('allids',{'ids':list(map(str,range(201)))}),('where',{'where':{'group':1}})]:
            try:
                q=c.query(query_embeddings=[[1.,0.]],n_results=k,**kw);out['calls'][f'{k}-{kind}']={'n':len(q['ids'][0]),'ids':q['ids'][0]}
            except Exception as e:out['calls'][f'{k}-{kind}']={'error':str(e)}
    return out
if len(sys.argv)>1:
    out={c.name:queries(c) for c in cl.list_collections()}
    (r/'reopened.json').write_text(json.dumps(out,indent=2));sys.exit()
out={}
for flavor in ['near','same','distinct']:
    vectors=([[.1235+(i-100)*1e-10,math.sqrt(1-(.1235+(i-100)*1e-10)**2)] for i in range(201)] if flavor=='near' else [[1.,0.]]*201 if flavor=='same' else [[math.cos(i*2*math.pi/201),math.sin(i*2*math.pi/201)] for i in range(201)])
    for ef in [100,1000]:
        name=f'{flavor}-{ef}'
        c=cl.create_collection(name,embedding_function=None,configuration={'hnsw':{'space':'cosine','ef_search':ef}})
        c.add(ids=list(map(str,range(201))),embeddings=vectors,metadatas=[{'group':1}]*201)
        out[name]=queries(c)
        out[name]['input_hash']=hashlib.sha256(np.array([v for _,v in sorted(zip(map(str,range(201)),vectors))],dtype='<f4').tobytes()).hexdigest()
        out[name]['unique_f32']=len(set(np.array(vectors,dtype='<f4').view('u1').reshape(201,-1).tobytes()[i*8:(i+1)*8] for i in range(201)))
(r/'initial.json').write_text(json.dumps(out,indent=2))
print({k:{'count':v['count'],'stored_equal':v['stored_hash']==v['input_hash'],'unique':v['unique_f32'],'query201':v['calls']['201-none']['n']} for k,v in out.items()})
