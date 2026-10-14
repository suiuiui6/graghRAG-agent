import hashlib
import json
import pathlib

root=pathlib.Path(__file__).resolve().parent
baseline=json.loads(next((root.parent).glob('filters-chroma-*.json')).read_text(encoding='utf-8'))
records=baseline['synthetic_rows']
for record,value,big in zip(records,[1,1.0,True,'1',1.5,None],[9007199254740992,9007199254740993,9007199254740994,2,3,4],strict=True):
    if value is not None: record['mixed']=value
    record['big']=big
records[0]["新字段'; DROP TABLE t; --"]='中文值'
records[1]["新字段'; DROP TABLE t; --"]='另一值'
cases=[case['where'] for case in baseline['cases']]
for key,value in [('active',1),('page',True),('missing_field','anything'),('mixed',1),('mixed',1.0),('mixed',True),('mixed','1')]:
    for op in ['$eq','$ne','$in','$nin']:
        case={key:{op:[value] if op in ('$in','$nin') else value}}
        if json.dumps(case,sort_keys=True) not in {json.dumps(x,sort_keys=True) for x in cases}: cases.append(case)
for key,value in [('page',1.5),('mixed',1),('mixed',1.0),('big',9007199254740993),('big',9007199254740992.0)]:
    for op in ['$eq','$ne','$gt','$gte','$lt','$lte']:
        case={key:{op:value}}
        if json.dumps(case,sort_keys=True) not in {json.dumps(x,sort_keys=True) for x in cases}: cases.append(case)
cases.extend([{"新字段'; DROP TABLE t; --":'中文值'},{"新字段'; DROP TABLE t; --":{'$ne':'中文值'}},{'mixed':{'$in':[1,1.5]}},{'mixed':{'$in':[True,1]}},{'$and':[{'mixed':{'$ne':1}},{'$or':[{'source':{'$nin':['s1']}},{'page':True}]}]}])
payload={'rows':records,'cases':cases,'purpose':'Fixed six synthetic rows, original18 plus bounded type/numeric/missing/quoted-key truth cases; no provider or product imports.'}
path=root/'fixtures.json'
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(cases),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
