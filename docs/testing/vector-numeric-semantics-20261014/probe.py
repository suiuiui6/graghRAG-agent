import chromadb
from chromadb.config import Settings
import math, sys, json, time, hashlib, operator, ctypes
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parents[1]/'docs/testing/vector-numeric-semantics-20261014'
LO,HI=-(2**63),2**63-1
values=[LO,LO+1,-2,-1,0,1,2,HI-1,HI,-1.5,1.5,float(LO),math.nextafter(float(LO),-math.inf),math.nextafter(float(LO),math.inf),float(2**63),math.nextafter(float(2**63),-math.inf),math.nextafter(float(2**63),math.inf),-1e100,1e100,-sys.float_info.max,sys.float_info.max,False,True]
rows=[{'id':f'r{i:02}', 'metadata':{'number':v,'float_only':float(v),'group':'all'}, 'vector':[float(i+1),1.,0.]} for i,v in enumerate(values)]
rows.append({'id':'missing','metadata':{'group':'all'},'vector':[30.,1.,0.]})
literals=[LO,LO+1,HI-1,HI,-1.5,1.5,-1e100,1e100,-sys.float_info.max,sys.float_info.max,float(LO),math.nextafter(float(LO),-math.inf),math.nextafter(float(LO),math.inf),float(2**63),math.nextafter(float(2**63),-math.inf),math.nextafter(float(2**63),math.inf)]
ops={'$eq':operator.eq,'$ne':operator.ne,'$gt':operator.gt,'$gte':operator.ge,'$lt':operator.lt,'$lte':operator.le}
def expected(key,op,q):
    if op in ('$in','$nin'):
        sets=[set(expected(key,'$eq' if op=='$in' else '$ne',v)) for v in q]
        return sorted(set.union(*sets) if op=='$in' else set.intersection(*sets))
    ids=[]
    for row in rows:
        v=row['metadata'].get(key)
        if type(v) not in (int,float):
            ok=op=='$ne'
        else:
            normalized=q
            if type(q) is float:
                normalized=next(report['readback'][r['id']]['number'] for r in rows[:-1] if type(r['metadata']['number']) is float and r['metadata']['number']==q)
            converted=min(HI,max(LO,math.trunc(normalized))) if type(v) is int else float(normalized)
            actual=report['readback'][row['id']][key]
            ok=ops[op](actual,converted)
        if ok: ids.append(row['id'])
    return sorted(ids)
db=chromadb.PersistentClient(path=str(ROOT/f'db-{time.time_ns()}'),settings=Settings(anonymized_telemetry=False))
c=db.create_collection('numeric_semantics',embedding_function=None)
c.add(ids=[r['id'] for r in rows],metadatas=[r['metadata'] for r in rows],embeddings=[r['vector'] for r in rows])
back=c.get()
report={'version':chromadb.__version__,'rows':rows,'readback':dict(zip(back['ids'],back['metadatas'])),'cases':[],'differences':[],'errors':[]}
assert chromadb.__version__=='1.5.9'
cases=[(key,op,q) for key in ['number','float_only','absent'] for q in literals for op in ops]
cases += [(key,op,q) for key in ['number','float_only','absent'] for q in [[-1e100,1e100],[-1.5,1.5],[LO,HI],[float(LO),float(2**63)]] for op in ['$in','$nin']]
for key,op,q in cases:
    where={key:{op:q}}
    want=expected(key,op,q)
    try: result={'status':'OK','ids':sorted(c.get(where=where)['ids'])}
    except Exception as e: result={'status':'REJECTED','class':type(e).__name__,'message':str(e)}
    entry={'where':where,'expected_saturating_model':want,**result}
    report['cases'].append(entry)
    if result.get('ids')!=want: report['differences'].append(entry)
extra=[{key:{op:([q] if op in ('$in','$nin') else q)}} for key in ['number','absent'] for q in [2**63,LO-1,float('inf'),float('-inf'),float('nan')] for op in list(ops)+['$in','$nin']]
for where in [{'number':{'$eq':True}},{'number':{'$in':[True,False]}},{'number':{'$gt':True}},{'number':{'$in':[1,1.5]}}]+extra:
    try: result={'status':'OK','ids':sorted(c.get(where=where)['ids'])}
    except Exception as e: result={'status':'REJECTED','class':type(e).__name__,'message':str(e)}
    report['errors'].append({'where':where,**result})
report['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['fixture_sha256']=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
(OUT/'oracle.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'version':report['version'],'cases':len(cases),'differences':len(report['differences']),'error_cases':len(report['errors'])}))
sys.exit(bool(report['differences']))
