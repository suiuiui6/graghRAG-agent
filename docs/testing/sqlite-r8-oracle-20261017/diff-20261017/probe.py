import math,json
import numpy as n
from pathlib import Path
r=Path(__file__).parent
actual=json.loads((r/'chroma.json').read_text())['boundary']
out={}
for method in ['divide','reciprocal']:
    rows=[]
    for i in range(201):
        v=.1235+(i-100)*1e-10;a=n.array([v,math.sqrt(1-v*v)],dtype='f4')
        norm=n.float32(n.sqrt(n.float32(n.float32(a[0]*a[0])+n.float32(a[1]*a[1])))+n.float32(1e-30))
        normalized=a/norm if method=='divide' else a*n.float32(1/norm)
        d=float(n.float32(n.float32(1)-normalized[0]));s=round(1-d/2,4)
        if s!=actual[str(i)]:rows.append({'id':i,'score':s,'actual':actual[str(i)]})
    out[method]=rows
(r/'probe.json').write_text(json.dumps(out,indent=2));print({k:len(v) for k,v in out.items()})
