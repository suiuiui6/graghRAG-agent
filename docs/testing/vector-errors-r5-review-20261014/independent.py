import pathlib,sys,tempfile,json,ast,types,concurrent.futures,logging,hashlib
from unittest.mock import patch
r=pathlib.Path(__file__).resolve().parent;repo=r.parents[1]
snapshot=sys.argv[1] if len(sys.argv)>1 else 'snapshot'
sys.path.insert(0,str(r/snapshot))
import generic_filter
from probe_store import ProbeStore,validate_vector
from vector_errors import VectorStoreError
out=[]
def check(label,fn,code):
 try:fn()
 except Exception as e:
  out.append({'label':label,'class':type(e).__name__,'code':getattr(e,'code',None)})
  assert isinstance(e,VectorStoreError) and e.code==code,(label,type(e),str(e))
 else:raise AssertionError(label+' accepted')
store=ProbeStore(tempfile.mkdtemp(dir=r,prefix='review-lance-'),[{'id':'review','metadata':{'p':-7,'flag':True,'s':'independent'}}])
assert store.search([1.,0.,0.],where={'p':-7})[0]['chunk_id']=='review'
assert store.search([1.,0.,0.],where={'p':77})==[]
for where in [{'p':{'$in':[False,0]}},{'unknown':{'$eq':2**63}},{'$and':[{'p':1}]}]:
 with patch.object(store.table,'search',side_effect=AssertionError('backend touched')):
  check('invalid '+repr(where),lambda:store.search([1.,0.,0.],where=where),'invalid_filter')
for cls in (ValueError,TypeError):
 cause=cls('INDEPENDENT_R5_PRIVATE_981')
 with patch.object(generic_filter,'col',side_effect=cause):
  check('native_compile_'+cls.__name__,lambda:store.search([1.,0.,0.],where={'p':-7}),'storage_unavailable')
ns={'ThreadPoolExecutor':concurrent.futures.ThreadPoolExecutor,'as_completed':concurrent.futures.as_completed}
for name in ['source_control','evidence_trace']:
 p=repo/'backend'/f'{name}.py';exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),ns)
p=repo/'backend/retrieval.py';tree=ast.parse(p.read_text(encoding='utf-8'))
names={'_search_vector_store_with_projection','_vector_recall','multi_path_recall'}
unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]],type_ignores=[])
exec(compile(ast.fix_missing_locations(unit),str(p),'exec'),ns)
lp=repo/'backend/logging_config.py';lns={'__name__':'independent_logging'};exec(compile(lp.read_text(encoding='utf-8'),str(lp),'exec'),lns)
logdir=r/('actual-logs-'+snapshot);lns['setup_logging'](str(logdir));ns['logger']=lns['get_logger']('review.independent')
cfg=types.SimpleNamespace(enabled_sources=('vector',),enable_multi_query=False,vector_top_k=3)
pre=types.SimpleNamespace(intent='general',original='same',rewritten='same')
def recall():
 trace={'stages':{}};v=ns['multi_path_recall'](pre,[[1.,0.,0.]],store,cfg,execution_trace=trace)
 return v,trace['stages']['normal']['vector']
assert recall()[1]['candidate_count']==1
original=store.search
with patch.object(store,'search',side_effect=lambda **kw:original(**kw,where={'p':77})):
 v,t=recall();assert t['status']=='executed' and t['candidate_count']==0
for cls in (TypeError,ValueError):
 before=store.search_calls;cause=cls('INDEPENDENT_R5_PRIVATE_981 api_key=sk-independent012345678901234567890123456789')
 with patch.object(store.table,'search',side_effect=cause):
  v,t=recall();assert v==[] and t['status']=='failed' and t['candidate_count'] is None
 assert store.search_calls-before==1
 out.append({'label':'consumer_'+cls.__name__,'trace':t,'calls':1})
log=(logdir/'app.log').read_text(encoding='utf-8')
assert 'INDEPENDENT_R5_PRIVATE_981' in log
assert 'sk-independent012345678901234567890123456789' not in log
# Probe the vector numeric conversion boundary; preserve unexpected failures.
try:check('oversize_integer_vector',lambda:store.search([10**400,0,0]),'invalid_input')
except AssertionError as e:out.append({'open_finding':str(e)})
# Real facade score and native constructor boundary, independent fixture IDs.
scores=ProbeStore(tempfile.mkdtemp(dir=r,prefix='review-score-'),[{'id':n,'metadata':{'p':j}} for j,n in enumerate(['north','east','south'])],[[0.,1.,0.],[1.,0.,0.],[0.,-1.,0.]])
got={x['chunk_id']:x['score'] for x in scores.search([0.,1.,0.])}
assert got=={'north':1.,'east':.5,'south':0.},got
with patch.object(generic_filter.pa,'schema',side_effect=TypeError('synthetic_constructor')):
 check('native_constructor',lambda:ProbeStore(str(r/'never-constructor'),[]),'storage_unavailable')
(r/('independent-result-'+snapshot+'.json')).write_text(json.dumps({'checks':out,'scores':got,'marker_residual':True,'key_redacted':True},indent=2))
print(json.dumps(out,indent=2))
