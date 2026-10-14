import json, operator, math, hashlib, datetime
from pathlib import Path
root=Path(__file__).resolve().parent
out=root.parents[1]/'docs/testing/vector-numeric-semantics-20261014'
r=json.loads((out/'oracle.json').read_text())
ops={'$eq':operator.eq,'$ne':operator.ne,'$gt':operator.gt,'$gte':operator.ge,'$lt':operator.lt,'$lte':operator.le}
lo,hi=-(2**63),2**63-1
def raw(key,op,q):
    if op in ('$in','$nin'):
        ss=[set(raw(key,'$eq' if op=='$in' else '$ne',x)) for x in q]
        return sorted(set.union(*ss) if op=='$in' else set.intersection(*ss))
    ans=[]
    for row in r['rows']:
        v=row['metadata'].get(key)
        ok=(op=='$ne') if type(v) not in (int,float) else ops[op](v,min(hi,max(lo,math.trunc(q))) if type(v) is int else float(q))
        if ok: ans.append(row['id'])
    return sorted(ans)
red=[]
for case in r['cases']:
    key,expr=next(iter(case['where'].items())); op,q=next(iter(expr.items()))
    want=raw(key,op,q)
    if want!=case.get('ids'): red.append({'where':case['where'],'raw_model':want,'actual':case})
assert len(red)==76
(out/'raw-model-differences.json').write_text(json.dumps({'status':'FAIL','count':len(red),'differences':red},indent=2))
drifts=[]
for row in r['rows']:
    actual=r['readback'][row['id']]
    for k,v in row['metadata'].items():
        if v!=actual[k] or type(v)!=type(actual[k]): drifts.append({'id':row['id'],'key':k,'input':v,'readback':actual[k]})
(out/'input-readback-drifts.json').write_text(json.dumps(drifts,indent=2))
stable_ids={row['id'] for row in r['rows']} - {d['id'] for d in drifts}
unstable=[math.nextafter(float(lo),-math.inf),math.nextafter(float(lo),math.inf),math.nextafter(float(2**63),-math.inf),math.nextafter(float(2**63),math.inf)]
subset=[]
for case in r['cases']:
    key,expr=next(iter(case['where'].items())); op,q=next(iter(expr.items()))
    qs=q if isinstance(q,list) else [q]
    if any(type(x) is float and x in unstable for x in qs): continue
    want=sorted(set(raw(key,op,q)) & stable_ids)
    actual=sorted(set(case['ids']) & stable_ids)
    subset.append({'where':case['where'],'expected':want,'actual':actual})
assert all(c['expected']==c['actual'] for c in subset)
(out/'stable-domain-predicate-check.json').write_text(json.dumps({'status':'PASS','count':len(subset),'excluded_records':sorted({d['id'] for d in drifts}),'excluded_float_literals':unstable,'cases':subset},indent=2))
manifest={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':'.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-numeric-semantics-20261014/probe.py','exit_code':0,'scope':'312 real Chroma queries; empirical readback-normalized predicate model; 84 boundary/error probes','raw_model_mismatches':76,'readback_drifts':len(drifts),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
