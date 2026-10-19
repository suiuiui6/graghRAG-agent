import ast, concurrent.futures, contextlib, hashlib, io, json, logging, pathlib, sys, tempfile, types
from unittest.mock import patch
root=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(root))
import safe_vector_logging as safe
from vector_errors import VectorStorageError
from probe_store import ProbeStore
MARK='INDEPENDENT_R6_PRIVATE_84015';calls=[]
class Meta(type):
 def __getattribute__(self,key):calls.append('meta');raise AssertionError('meta')
class Unknown(VectorStorageError,metaclass=Meta):
 def __getattribute__(self,key):calls.append('attr');raise AssertionError('attr')
 def __str__(self):calls.append('str');raise AssertionError('str')
 def __repr__(self):calls.append('repr');raise AssertionError('repr')
def new_unknown():
 e=BaseException.__new__(Unknown)
 BaseException.__dict__['__dict__'].__get__(e).update(code='storage_unavailable',operation='search')
 return e
class Fake:
 @property
 def __class__(self):calls.append('fakeclass');raise AssertionError('fakeclass')
# A nonexception must not execute its __class__ accessor during detection.
fakeevent={'event':'ordinary','exc_info':Fake()}
assert safe.processor(None,'error',fakeevent) is fakeevent
def audited_raise(error):raise error
safe.register(audited_raise.__code__,'review_fixture.py','audited_raise')
typed=new_unknown();cause=type(MARK,(Exception,),{})(MARK)
BaseException.__cause__.__set__(typed,cause)
wrapper=RuntimeError(MARK);wrapper.__cause__=typed
BaseException.__context__.__set__(cause,wrapper)
try:audited_raise(wrapper)
except RuntimeError:pass
forged=types.FunctionType(audited_raise.__code__.replace(co_filename=MARK,co_name=MARK),globals())
try:forged(typed)
except BaseException:pass
tail=typed
for i in range(600):
 e=RuntimeError(MARK);e.__cause__=tail;tail=e
ordinary=RuntimeError(MARK)
for i in range(40):
 e=RuntimeError(MARK);e.__cause__=ordinary;ordinary=e
lns={'__name__':'review_logging'};logpath=root/'current-consumer/logging_config.py'
exec(compile(logpath.read_text(encoding='utf-8'),str(logpath),'exec'),lns)
logdir=pathlib.Path(tempfile.mkdtemp(prefix='actual-logs-',dir=out));console=io.StringIO()
import structlog
with contextlib.redirect_stderr(console):lns['setup_logging'](str(logdir))
cfg=structlog.get_config();procs=list(cfg['processors']);procs.insert(procs.index(structlog.processors.format_exc_info),safe.processor);structlog.configure(processors=procs)
logger=lns['get_logger'](MARK);structlog.contextvars.bind_contextvars(raw=MARK)
tampered=new_unknown();BaseException.__dict__['__dict__'].__get__(tampered).update(code=MARK,operation=MARK,retryable=Fake())
for error in (typed,wrapper,tail,ordinary,tampered):
 logger.error(MARK,exc_info=(type(error),error,None),error=MARK,exception=MARK,extra={'nested':[MARK,typed,Fake()]},status=MARK,candidate_count=MARK)
# Current real consumer AST subset, with actual table success/zero and injected failure.
ns={'ThreadPoolExecutor':concurrent.futures.ThreadPoolExecutor,'as_completed':concurrent.futures.as_completed}
for name in ('source_control','evidence_trace'):
 path=root/'current-consumer'/f'{name}.py';exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),ns)
path=root/'current-consumer/retrieval.py';tree=ast.parse(path.read_text(encoding='utf-8'))
names={'_search_vector_store_with_projection','_vector_recall','multi_path_recall'}
selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(selected)==3
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*selected],type_ignores=[])),str(path),'exec'),ns)
for name in names:safe.register(ns[name].__code__,'retrieval.py',name)
ns['logger']=logger
store=ProbeStore(tempfile.mkdtemp(prefix='actual-lance-',dir=out),[{'id':'new','metadata':{'n':1}}])
cfg=types.SimpleNamespace(enabled_sources=('vector',),enable_multi_query=False,vector_top_k=3)
pre=types.SimpleNamespace(intent='general',original='q',rewritten='q');receipts=[]
def run():
 trace={'stages':{}};before=store.search_calls
 result=ns['multi_path_recall'](pre,[[1.,0.,0.]],store,cfg,execution_trace=trace)
 assert store.search_calls-before==1
 return result,trace['stages']['normal']['vector']
result,trace=run();assert trace['status']=='executed' and trace['candidate_count']==1;receipts.append(trace)
original=store.search
with patch.object(store,'search',side_effect=lambda **kw:original(**kw,where={'n':8})):
 result,trace=run();assert result==[] and trace['status']=='executed' and trace['candidate_count']==0;receipts.append(trace)
with patch.object(store.table,'search',side_effect=ValueError(MARK)):
 result,trace=run();assert result==[] and trace['status']=='failed' and trace['candidate_count'] is None;receipts.append(trace)
for h in logging.getLogger().handlers:h.flush()
file=(logdir/'app.log').read_text(encoding='utf-8');text=console.getvalue()
(out/'independent-console.log').write_text(text,encoding='utf-8');(out/'independent-file.log').write_text(file,encoding='utf-8')
assert MARK not in file and MARK not in text
events=[json.loads(line) for line in file.splitlines() if line.strip()]
assert len(events)==6
assert all(e['event']=='vector_store_failure' for e in events)
assert any(e['vector_error']['cycle_or_shared'] for e in events)
assert any(e['vector_error']['truncated'] for e in events)
assert events[4]['vector_error']['code']=='unknown' and events[4]['vector_error']['operation']=='unknown'
assert any(f['file']=='unknown_frame' for e in events for f in e['vector_error']['frames'])
assert any(f['file']=='review_fixture.py' for e in events for f in e['vector_error']['frames'])
assert any(f['file']=='retrieval.py' for e in events for f in e['vector_error']['frames'])
assert BaseException.__cause__.__get__(typed) is cause and wrapper.__cause__ is typed
assert calls==[]
structlog.contextvars.clear_contextvars()
receipt={'passed':True,'events':len(events),'user_code_calls':calls,'cause_preserved':True,'consumer_scope':'3 actual frozen AST functions, real Lance success/zero; injected backend ValueError failure','consumer_results':receipts,'inputs':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'safe_vector_logging.py',root/'generic_filter.py',*sorted((root/'current-consumer').glob('*.py'))]}}
(out/'independent-logging.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'events':len(events),'user_code_calls':calls}))
