import ast,concurrent.futures,contextlib,io,json,logging,math,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
from probe_store import ProbeStore
from generic_filter import StaticProjection
from vector_errors import *
r=pathlib.Path(__file__).resolve().parent
MARK='R6_BARE_PRIVATE_528194'
class Tests(unittest.TestCase):
 def test_wide_records(self):
  for v in [2**63,2**64,-2**63-1,2**63+1025,-2**63-1025,10**100,10**308]:
   p=StaticProjection([{'id':'w','metadata':{'n':v}}]); row=p.encode({'id':'w','metadata':{'n':v}})
   self.assertEqual(json.loads(row['metadata_json'])['n'],v)
   self.assertIs(type(json.loads(row['compat_metadata_json'])['n']),float)
   self.assertEqual(row['m0_type'],'float')
  for v in [10**309,-10**400]:
   with self.assertRaises(VectorInputError):StaticProjection([{'id':'w','metadata':{'n':v}}])
 def test_nonfinite_policy(self):
  s=ProbeStore(tempfile.mkdtemp(dir=r),[{'id':'a','metadata':{'n':1}}])
  for kind in (list,tuple):
   for i in range(3):
    for bad in (math.nan,math.inf,-math.inf):
     v=[1.,0.,0.];v[i]=bad
     with patch.object(s.table,'search',side_effect=AssertionError('must not run')) as backend:
      with self.assertRaises(VectorInputError) as e:s.search(kind(v))
      self.assertEqual(e.exception.code,'invalid_input');backend.assert_not_called()
  self.assertEqual(s.search([1.,0.,0.])[0]['chunk_id'],'a')
 def test_logging_and_real_consumer(self):
  import safe_vector_logging as safe
  ns={'ThreadPoolExecutor':concurrent.futures.ThreadPoolExecutor,'as_completed':concurrent.futures.as_completed}
  for name in ['source_control','evidence_trace']:
   p=r/'current-consumer'/f'{name}.py';exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),ns)
  path=r/'current-consumer/retrieval.py';tree=ast.parse(path.read_text(encoding='utf-8'));names={'_search_vector_store_with_projection','_vector_recall','multi_path_recall'}
  selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*selected],type_ignores=[])),str(path),'exec'),ns)
  for name in names:safe.register(ns[name].__code__,'retrieval.py',name)
  lns={'__name__':'r6_logging'};lp=r/'current-consumer/logging_config.py';exec(compile(lp.read_text(encoding='utf-8'),str(lp),'exec'),lns)
  logdir=pathlib.Path(tempfile.mkdtemp(dir=r));console=io.StringIO()
  import structlog
  with contextlib.redirect_stderr(console):lns['setup_logging'](str(logdir))
  cfg=structlog.get_config();procs=list(cfg['processors']);procs.insert(procs.index(structlog.processors.format_exc_info),safe.processor);structlog.configure(processors=procs)
  logger=lns['get_logger'](MARK);ns['logger']=logger
  structlog.contextvars.bind_contextvars(raw=MARK)
  s=ProbeStore(tempfile.mkdtemp(dir=r),[{'id':'a','metadata':{'n':1}}]);config=types.SimpleNamespace(enabled_sources=('vector',),enable_multi_query=False,vector_top_k=2);pre=types.SimpleNamespace(intent='general',original='same',rewritten='same')
  trace={'stages':{}}
  with patch.object(s.table,'search',side_effect=ValueError(MARK)):
   result=ns['multi_path_recall'](pre,[[1.,0.,0.]],s,config,execution_trace=trace)
  self.assertEqual(result,[]);self.assertEqual(trace['stages']['normal']['vector']['status'],'failed');self.assertIsNone(trace['stages']['normal']['vector']['candidate_count']);self.assertEqual(s.search_calls,1)
  class Evil(Exception):
   def __str__(self):raise AssertionError('str called')
   def __repr__(self):raise AssertionError('repr called')
   def __getattribute__(self,k):raise AssertionError('attribute called')
  evil=Evil(MARK);typed=VectorStorageError('storage_unavailable','search');typed.__cause__=evil
  wrapper=RuntimeError(MARK);wrapper.__cause__=typed;evil.__context__=wrapper
  class SubStorage(VectorStorageError):pass
  subclass=SubStorage('storage_unavailable','search');subclass.__cause__=ValueError(MARK)
  logger.error(MARK,exc_info=(type(subclass),subclass,None),error=MARK,nested={'raw':MARK})
  class HostileMeta(type):
   def __getattribute__(self,key):raise AssertionError('metaclass access')
  class HostileStorage(SubStorage,metaclass=HostileMeta):
   def __init__(self,*args):BaseException.__init__(self,*args)
   def __getattribute__(self,key):raise AssertionError('instance access')
  hostile=HostileStorage('storage_unavailable','search');hostile.__cause__=ValueError(MARK)
  logger.error(MARK,exc_info=hostile,error=MARK)
  class Fake:
   @property
   def __class__(self):raise AssertionError('fake class access')
  ordinary={'exc_info':Fake(),'event':'ordinary'}
  self.assertIs(safe.processor(None,'error',ordinary),ordinary)
  shared=VectorStorageError('storage_unavailable','search');cause=ValueError(MARK)
  shared.__cause__=cause;shared.__context__=cause
  diagnostic=safe.processor(None,'error',{'exc_info':shared,'event':MARK})['vector_error']
  self.assertTrue(diagnostic['cycle_or_shared']);self.assertEqual(len(diagnostic['chain']),2)
  forged=compile('raise error',MARK,'exec');scope={'error':wrapper}
  try:exec(forged,scope)
  except RuntimeError:
   logger.error(MARK,exc_info=True,error=MARK,nested={'raw':MARK},status=MARK,candidate_count=MARK)
  # Long chain remains bounded and unknown dynamic class names never escape.
  tail=typed
  for _ in range(64):
   e=type(MARK,(Exception,),{})(MARK);e.__cause__=tail;tail=e
  logger.error(MARK,exc_info=(type(tail),tail,None),extra=MARK)
  for handler in logging.getLogger().handlers:handler.flush()
  file=(logdir/'app.log').read_text(encoding='utf-8');out=console.getvalue()
  (r/'r6-console.log').write_text(out,encoding='utf-8');(r/'r6-file.log').write_text(file,encoding='utf-8')
  self.assertNotIn(MARK,file);self.assertNotIn(MARK,out)
  events=[json.loads(line) for line in file.splitlines() if line.strip()];typed_events=[e for e in events if e.get('event')=='vector_store_failure']
  self.assertGreaterEqual(len(typed_events),5);self.assertTrue(any(e['vector_error']['frames'] for e in typed_events));self.assertTrue(any(e['vector_error']['cycle_or_shared'] for e in typed_events));self.assertTrue(any(e['vector_error']['truncated'] for e in typed_events))
  self.assertIs(wrapper.__cause__,typed);self.assertIs(typed.__cause__,evil)
  structlog.contextvars.clear_contextvars()
if __name__=='__main__':unittest.main(verbosity=2)
