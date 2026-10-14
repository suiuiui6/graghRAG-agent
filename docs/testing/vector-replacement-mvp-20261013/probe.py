import concurrent.futures
from datetime import timedelta
import functools
import hashlib
import importlib.metadata
import json
import operator
import pathlib
import platform
import subprocess
import sys
import time
import traceback

import lancedb
import numpy as np
import pyarrow as pa
from lancedb.expr import col, lit

ROOT = pathlib.Path(__file__).resolve().parent
DB = ROOT / f'synthetic-db-{time.time_ns()}'
RESULT = ROOT / f'results-{time.time_ns()}.json'
checks = []

def check(name, fn):
    started = time.perf_counter()
    try:
        detail = fn()
        checks.append(dict(name=name, status='PASS', seconds=time.perf_counter()-started, detail=detail))
    except Exception as exc:
        checks.append(dict(name=name, status='FAIL', seconds=time.perf_counter()-started, error=repr(exc), trace=traceback.format_exc()))
    print(json.dumps(checks[-1], ensure_ascii=True), flush=True)

FIELDS = {'id', 'source', 'page', 'active'}
FIELD_TYPES = {'id':str,'source':str,'page':int,'active':bool}
def predicate(value, depth=0):
    if depth > 8 or not isinstance(value, dict) or len(value) != 1:
        raise ValueError('invalid bounded filter')
    key, arg = next(iter(value.items()))
    if key in ('$and', '$or'):
        if not isinstance(arg, list) or not 2 <= len(arg) <= 32:
            raise ValueError('invalid logical operands')
        return functools.reduce(operator.and_ if key == '$and' else operator.or_, [predicate(x, depth+1) for x in arg])
    if key not in FIELDS:
        raise ValueError('unknown field')
    if not isinstance(arg, dict):
        arg = {'$eq': arg}
    if len(arg) != 1:
        raise ValueError('invalid comparison')
    op, val = next(iter(arg.items()))
    if op in ('$in', '$nin'):
        if not isinstance(val, list) or not 1 <= len(val) <= 32:
            raise ValueError('invalid membership')
        if any(type(x) is not FIELD_TYPES[key] for x in val):
            raise ValueError('invalid field literal type')
        parts = [col(key) == lit(x) if op == '$in' else col(key) != lit(x) for x in val]
        return functools.reduce(operator.or_ if op == '$in' else operator.and_, parts)
    methods = {'$eq':'eq', '$ne':'ne', '$gt':'gt', '$gte':'gte', '$lt':'lt', '$lte':'lte'}
    if op not in methods or type(val) is not FIELD_TYPES[key]:
        raise ValueError('invalid comparison')
    return getattr(col(key), methods[op])(lit(val))

schema = pa.schema([('id',pa.string()), ('text',pa.string()), ('source',pa.string()), ('page',pa.int64()), ('active',pa.bool_()), ('metadata_json',pa.string()), ('vector',pa.list_(pa.float32(),3))])
rows = [dict(id=x, text='合成文本'+x, source=s, page=p, active=a, metadata_json=json.dumps({'n':p,'flag':a,'float':1.25,'nested':{'x':['中文',None]}},ensure_ascii=False),vector=v) for x,s,p,a,v in [('a','s1',1,True,[1.,0.,0.]),('b','s1',2,False,[0.,1.,0.]),('c',"x' OR 1=1 --",3,True,[-1.,0.,0.])]]
db = lancedb.connect(DB, read_consistency_interval=timedelta(0))
table = None
def small():
    global table
    table = db.create_table('small',rows,schema=schema)
    got=table.search().where(predicate({'id':'a'})).to_list()
    assert len(got)==1 and got[0]['text']==rows[0]['text']
    assert json.loads(got[0]['metadata_json'])==json.loads(rows[0]['metadata_json'])
    assert type(got[0]['page']) is int and type(got[0]['active']) is bool
    return {'count':table.count_rows(),'metadata':json.loads(got[0]['metadata_json'])}
check('small_real_io_metadata',small)
def precision():
    original=np.array([0.123456789012345,1.0000000000000002,-0.987654321098765],dtype='<f8')
    original_bytes=original.tobytes()
    s=pa.schema([('id',pa.string()),('vector',pa.list_(pa.float32(),3)),('original_vector',pa.binary()),('original_dtype',pa.string())])
    t=db.create_table('precision',[{'id':'precision','vector':original.tolist(),'original_vector':original_bytes,'original_dtype':'<f8'}],schema=s)
    restored=t.search().to_list()[0]
    assert restored['original_vector']==original_bytes and restored['original_dtype']=='<f8'
    derived=np.asarray(restored['vector'],dtype=np.float64)
    assert not np.array_equal(derived,original)
    return {'original_bytes_sha256':hashlib.sha256(original_bytes).hexdigest(),'raw_binary_roundtrip_exact':True,'float32_derived_loss_max':float(np.max(np.abs(derived-original))),'original_dtype':'<f8','float32_is_not_lossless':True}
check('binary64_original_and_derived_precision',precision)
def filters():
    cases=[({'$and':[{'source':'s1'},{'page':{'$gte':2}}]},['b']),({'$or':[{'id':{'$in':['a','c']}},{'page':{'$lt':0}}]},['a','c']),({'source':"x' OR 1=1 --"},['c']),({'page':{'$ne':2}},['a','c']),({'page':{'$gt':1}},['b','c']),({'page':{'$lte':2}},['a','b']),({'id':{'$nin':['a','b']}},['c'])]
    for query, expected in cases:
        assert sorted(x['id'] for x in table.search().where(predicate(query)).to_list())==expected
    invalids=[{'id; DROP TABLE small':'a'},{'id':{'$like':'%'}},{'$and':[]},{'page':True},{'active':1},{'id':{'$in':[]}},{'id':{'$in':['a',1]}},{'id':{'$eq':'a','$ne':'b'}}]
    for invalid in invalids:
        try: predicate(invalid)
        except ValueError: pass
        else: raise AssertionError('unsafe filter accepted')
    return {'cases':len(cases),'unsafe_rejected':len(invalids),'typed_fields':True,'chroma_differential_not_run':True}
check('bounded_expr_filters',filters)
def cosine():
    result=table.search([1.,0.,0.]).distance_type('cosine').limit(3).to_list()
    assert [x['id'] for x in result]==['a','b','c']
    assert np.allclose([x['_distance'] for x in result],[0,1,2],atol=1e-6)
    return [{'id':x['id'],'distance':x['_distance'],'score':round((2.-x['_distance'])/2.,4)} for x in result]
check('cosine_score_mapping',cosine)
def duplicate():
    table.add([rows[0]])
    duplicates=table.search().where(predicate({'id':'a'})).to_list()
    assert len(duplicates)==2
    table.delete(predicate({'id':'a'}))
    table.add([rows[0]])
    return {'native_add_allows_duplicates':True,'adapter_must_preserve_unique_id':True}
check('duplicate_native_boundary',duplicate)
def invalid_write():
    before=table.count_rows(); errors=[]
    for bad in [dict(rows[0],vector=[1.,2.]),dict(rows[0],page='not-an-int')]:
        try: table.add([dict(rows[1],id='would-be-partial'),bad])
        except Exception as exc: errors.append(type(exc).__name__+': '+str(exc)[:300])
        else: raise AssertionError('invalid write accepted')
        assert table.count_rows()==before
    table.add([dict(rows[1],id='recovered')]); table.delete(predicate({'id':'recovered'}))
    return {'errors':errors,'count_stable':before}
check('failed_batch_atomicity_recovery',invalid_write)
def invalid_query():
    try: table.search([1.,2.]).distance_type('cosine').limit(2).to_list()
    except Exception as exc: return {'dimension_rejected':type(exc).__name__+': '+str(exc)[:300]}
    raise AssertionError('invalid query dimension accepted')
check('invalid_query_dimension',invalid_query)
def reopen():
    code="import lancedb,json; t=lancedb.connect("+repr(str(DB))+ ").open_table('small'); print(json.dumps({'count':t.count_rows(),'ids':sorted(x['id'] for x in t.search().to_list())}))"
    p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=45)
    assert p.returncode==0,p.stderr
    data=json.loads(p.stdout); assert data=={'count':3,'ids':['a','b','c']}
    return data
check('new_process_persistence',reopen)
def visibility():
    code="import lancedb,json; t=lancedb.connect("+repr(str(DB))+").open_table('small'); t.add([json.loads("+repr(json.dumps(dict(rows[0],id='child-write')))+")])"
    p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=45)
    assert p.returncode==0,p.stderr
    assert table.count_rows()==4
    table.delete(predicate({'id':'child-write'}))
    return {'existing_connection_observes_child_commit':True,'read_consistency_interval_seconds':0}
check('cross_process_visibility',visibility)
def deletion():
    table.delete(predicate({'id':{'$in':['a']}})); assert table.count_rows()==2
    table.delete(predicate({'source':'s1'})); assert table.count_rows()==1
    table.delete(lit(True)); assert table.count_rows()==0
    table.add(rows); assert table.count_rows()==3
    return {'id_source_clear_restore':True}
check('deletion_clear_restore',deletion)
def concurrency():
    def writer(i):
        t=lancedb.connect(DB).open_table('small')
        t.add([dict(rows[0],id=f'parallel-{i}')])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: list(ex.map(writer,range(12)))
    current=lancedb.connect(DB).open_table('small')
    assert current.count_rows()==15
    ids=[x['id'] for x in current.search().limit(100).to_list()]
    assert len(set(ids))==15
    return {'independent_connections':12,'threads':4,'count':15,'not_proof_of_multi_process_or_kill_atomicity':True}
check('concurrent_append',concurrency)
def scale():
    assert all(c['status']=='PASS' for c in checks),'small IO gate failed; scale not run'
    rng=np.random.default_rng(20261013); vectors=rng.normal(size=(5000,512)).astype('float32')
    data=pa.table({'id':[f'scale-{i}' for i in range(5000)],'text':['合成规模文本']*5000,'source':[f's-{i%10}' for i in range(5000)],'vector':pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel()),512)})
    start=time.perf_counter(); large=db.create_table('scale',data); write=time.perf_counter()-start
    assert large.count_rows()==5000
    times=[]
    for i in range(30):
        start=time.perf_counter(); result=large.search(vectors[i]).distance_type('cosine').limit(10).to_list(); times.append(time.perf_counter()-start)
        assert result[0]['id']==f'scale-{i}' and abs(result[0]['_distance'])<1e-5
    filtered=large.search(vectors[0]).distance_type('cosine').where(col('source')==lit('s-0')).limit(10).to_list()
    assert all(x['source']=='s-0' for x in filtered)
    return {'rows':5000,'dimensions':512,'write_seconds':write,'queries':30,'query_ms_p50':float(np.percentile(times,50)*1000),'query_ms_p95':float(np.percentile(times,95)*1000),'exact_scan_no_ann':True}
check('synthetic_5000x512',scale)
report={'python':sys.version,'platform':platform.platform(),'versions':{x:importlib.metadata.version(x) for x in ('lancedb','numpy','pyarrow')},'probe_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'checks':checks}
RESULT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('RESULT',RESULT,flush=True)
sys.exit(0 if all(x['status']=='PASS' for x in checks) else 1)
