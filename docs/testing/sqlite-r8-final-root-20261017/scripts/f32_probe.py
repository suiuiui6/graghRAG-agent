import json,math,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
src=root.parent/'sqlite-r8-oracle-20261016/score-boundary.json'
data=json.loads(src.read_text())
rows=[]
for case in data['score_mismatches']:
    v=np.asarray(case['vector'],dtype=np.float32)
    norm=np.float32(0)
    for x in v: norm=np.float32(norm+np.float32(x*x))
    norm=np.float32(np.sqrt(norm))
    unit=v/norm if norm else v
    dot=np.float32(unit[0])
    distance=float(np.float32(np.float32(1)-dot))
    rows.append({'id':case['id'],'distance':distance,'oracle_distance':case['distance'],'score':round(1-distance/2,4),'oracle_score':case['actual']})
result={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'numpy':np.__version__,'scope':'81 saved counterexamples only; no general HNSW equivalence claim','tested':len(rows),'distance_mismatches':sum(x['distance']!=x['oracle_distance'] for x in rows),'score_mismatches':sum(x['score']!=x['oracle_score'] for x in rows),'rows':rows}
(root/'f32-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print({k:v for k,v in result.items() if k!='rows'})
