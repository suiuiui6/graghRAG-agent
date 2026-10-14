import json
import pathlib
import sys
import time

root=pathlib.Path(__file__).resolve().parent
run=time.time_ns()
records=[
    {'id':'a','source':'s1','page':1,'active':True},
    {'id':'b','page':2,'active':False},
    {'id':'c','source':"中文' OR 1=1 --",'page':3,'active':True},
    {'id':'d','source':'s2'},
    {'id':'e','source':'s1','page':0,'active':False},
    {'id':'f','source':'','page':4,'active':True},
]
cases=[{'source':'s1'},{'source':{'$eq':"中文' OR 1=1 --"}},{'source':{'$ne':'s1'}},{'page':{'$gt':1}},{'page':{'$gte':2}},{'page':{'$lt':3}},{'page':{'$lte':2}},{'source':{'$in':['s1','s2']}},{'source':{'$nin':['s1']}},{'$and':[{'source':'s1'},{'page':{'$gt':0}}]},{'$or':[{'source':'s2'},{'active':True}]},{'active':True},{'active':1},{'page':True},{'source':{'$in':[]}},{'source':{'$in':['s1',1]}},{'source':{'$eq':'s1','$ne':'s2'}},{'missing_field':{'$ne':'anything'}}]
mode=sys.argv[1]
results=[]
if mode=='chroma':
    import chromadb
    from chromadb.config import Settings
    client=chromadb.PersistentClient(path=str(root/f'chroma-differential-{run}'),settings=Settings(anonymized_telemetry=False))
    collection=client.create_collection('synthetic_filters',embedding_function=None,metadata={'hnsw:space':'cosine'})
    collection.add(ids=[r['id'] for r in records],documents=['合成']*6,embeddings=[[1.,0.,0.]]*6,metadatas=[{k:v for k,v in r.items() if k!='id'} for r in records])
    query=lambda c: sorted(collection.get(where=c)['ids'])
    version=chromadb.__version__
else:
    import functools
    import operator
    import lancedb
    import pyarrow as pa
    from lancedb.expr import col,lit
    types={'source':str,'page':int,'active':bool}
    def mapped(c,depth=0):
        if depth>8 or not isinstance(c,dict) or len(c)!=1: raise ValueError('shape')
        k,v=next(iter(c.items()))
        if k in ('$and','$or'):
            if not isinstance(v,list) or not 2<=len(v)<=32: raise ValueError('logic')
            return functools.reduce(operator.and_ if k=='$and' else operator.or_,[mapped(x,depth+1) for x in v])
        if k not in types: raise ValueError('unknown field')
        v=v if isinstance(v,dict) else {'$eq':v}
        if len(v)!=1: raise ValueError('comparison shape')
        op,val=next(iter(v.items()))
        if op in ('$in','$nin'):
            if not isinstance(val,list) or not 1<=len(val)<=32 or any(type(x) is not types[k] for x in val): raise ValueError('membership')
            return functools.reduce(operator.or_ if op=='$in' else operator.and_,[(col(k)==lit(x)) if op=='$in' else (col(k)!=lit(x)) for x in val])
        ops={'$eq':'eq','$ne':'ne','$gt':'gt','$gte':'gte','$lt':'lt','$lte':'lte'}
        if op not in ops or type(val) is not types[k]: raise ValueError('literal type')
        return getattr(col(k),ops[op])(lit(val))
    db=lancedb.connect(root/f'lance-differential-{run}')
    schema=pa.schema([('id',pa.string()),('source',pa.string()),('page',pa.int64()),('active',pa.bool_()),('vector',pa.list_(pa.float32(),3))])
    table=db.create_table('filters',[{**{k:r.get(k) for k in ['id','source','page','active']},'vector':[1.,0.,0.]} for r in records],schema=schema)
    query=lambda c: sorted(r['id'] for r in table.search().where(mapped(c)).limit(100).to_list())
    version=lancedb.__version__
for case in cases:
    try: results.append({'where':case,'ids':query(case),'status':'OK'})
    except Exception as exc: results.append({'where':case,'status':'REJECTED','error':type(exc).__name__+': '+str(exc)[:400]})
result={'mode':mode,'version':version,'synthetic_rows':records,'cases':results}
(root/f'filters-{mode}-{run}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
