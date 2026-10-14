import ast,concurrent.futures,hashlib,io,json,logging,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
from generic_filter import StaticProjection
import generic_filter
from probe_store import ProbeStore
from vector_errors import *
r=pathlib.Path(__file__).resolve().parent; repo=r.parents[1]; SENTINEL='SYNTHETIC_PRIVATE_R5_741'; KEY='sk-'+'R5syntheticsecret012345678901234567890123'
class Contract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.store=ProbeStore(tempfile.mkdtemp(prefix='real-lance-',dir=r),[{'id':'a','metadata':{'n':1,'s':'ok'}}])
 def error(self, fn,code,operation=None,cause=None):
  with self.assertRaises(VectorStoreError) as caught:fn()
  e=caught.exception;self.assertEqual(e.code,code)
  if operation:self.assertEqual(e.operation,operation)
  self.assertFalse(e.retryable);self.assertNotIsInstance(e,TypeError)
  self.assertNotIn(SENTINEL,str(e));self.assertNotIn(SENTINEL,json.dumps(e.public_dict()))
  if code=='storage_unavailable':self.assertNotIsInstance(e,ValueError);self.assertIsNotNone(e.__cause__)
  else:self.assertIsInstance(e,ValueError) if code.startswith('invalid') else None
  if cause:self.assertIsInstance(e.__cause__,cause)
  return e
 def test_input_rejection(self):
  p=self.store.projection
  for where in [{'n':{'$in':[]}}, {'n':{'$in':[1,'x']}},{'n':2**63},{'n':10**400},{'n':float('inf')},{'n':{'$bad':1}}]:
   with patch.object(self.store.table,'search',side_effect=AssertionError('backend executed')):
    self.error(lambda:self.store.search([1.,0.,0.],where=where),'invalid_filter')
  for meta in [{'a':1,2:3},{'n':2**63},{'n':None},{'n':float('nan')}]:self.error(lambda:StaticProjection([{'id':'z','metadata':meta}]),'invalid_input')
  self.error(lambda:p.encode({'id':'z','metadata':{'new':1}}),'unsupported_capability')
  self.error(lambda:self.store.search([1,2]),'invalid_dimension','search')
  self.error(lambda:self.store.search([1,float('nan'),0]),'invalid_input','search')
  e=self.error(lambda:ProbeStore(str(r/'never'),[{'id':'a','metadata':{}}],[]),'invalid_input');self.assertIn('Length mismatch',str(e))
 def test_success(self):
  self.assertEqual(self.store.count(),1);self.assertEqual(len(self.store.scan()),1)
  self.assertEqual(self.store.search([1.,0.,0.])[0]['chunk_id'],'a')
  self.assertEqual(self.store.read({'n':99}),[])
  self.assertEqual(self.store.search([1.,0.,0.],where={'n':99}),[])
 def test_real_bad_path(self):
  bad=r/'ordinary-file';bad.write_text('synthetic ordinary file')
  self.error(lambda:ProbeStore(str(bad),[{'id':'a','metadata':{}}]),'storage_unavailable','open')
 def test_native_faults_and_baseexception(self):
  for cls in (ValueError,TypeError,OSError):
   with patch.object(generic_filter,'col',side_effect=cls(SENTINEL)):
    self.error(lambda:self.store.projection.compile({'n':1}),'storage_unavailable','compile',cls)
   with patch.object(self.store.table,'search',side_effect=cls(SENTINEL)):
    self.error(lambda:self.store.search([1.,0.,0.]),'storage_unavailable','search',cls)
  for operation,action in [('read',lambda:self.store.read({'n':1})),('count',self.store.count),('scan',self.store.scan)]:
   method='count_rows' if operation=='count' else 'search'
   with patch.object(self.store.table,method,side_effect=ValueError(SENTINEL)):
    self.error(action,'storage_unavailable',operation,ValueError)
  with patch.object(generic_filter,'col',side_effect=KeyboardInterrupt()):
   with self.assertRaises(KeyboardInterrupt):self.store.projection.compile({'n':1})
  with patch.object(self.store.table,'search',side_effect=SystemExit(9)):
   with self.assertRaises(SystemExit):self.store.search([1.,0.,0.])
 def test_real_consumers(self):
  ns={'ThreadPoolExecutor':concurrent.futures.ThreadPoolExecutor,'as_completed':concurrent.futures.as_completed}
  for name in ['source_control','evidence_trace']:
   path=repo/'backend'/f'{name}.py';exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),ns)
  path=repo/'backend/retrieval.py';tree=ast.parse(path.read_text(encoding='utf-8'));names={'_search_vector_store_with_projection','_vector_recall','multi_path_recall'}
  selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*selected],type_ignores=[])
  exec(compile(ast.fix_missing_locations(unit),str(path),'exec'),ns)
  # Real production logging setup, no config or .env imports.
  logpath=repo/'backend/logging_config.py'; lns={'__name__':'r5_logging'};exec(compile(logpath.read_text(encoding='utf-8'),str(logpath),'exec'),lns)
  logdir=pathlib.Path(tempfile.mkdtemp(prefix='consumer-logs-',dir=r));lns['setup_logging'](str(logdir));ns['logger']=lns['get_logger']('r5.consumer')
  config=types.SimpleNamespace(enabled_sources=('vector',),enable_multi_query=False,vector_top_k=2)
  pre=types.SimpleNamespace(intent='general',original='same',rewritten='same')
  receipts=[]
  def run():
   trace={'stages':{}};result=ns['multi_path_recall'](pre,[[1.,0.,0.]],self.store,config,execution_trace=trace)
   return result,trace['stages']['normal']['vector']
  before=self.store.search_calls;result,trace=run();self.assertEqual(trace['status'],'executed');self.assertEqual(trace['candidate_count'],1);self.assertEqual(self.store.search_calls-before,1)
  # Actual table no-match drives actual collector zero-count branch.
  with patch.object(self.store.table,'search',wraps=self.store.table.search) as search:
   original=self.store.search
   with patch.object(self.store,'search',side_effect=lambda **kw:original(**kw,where={'n':99})):
    result,trace=run();self.assertEqual(trace['status'],'executed');self.assertEqual(trace['candidate_count'],0)
  for cls in (ValueError,TypeError):
   before=self.store.search_calls
   with patch.object(self.store.table,'search',side_effect=cls(SENTINEL+' api_key='+KEY)):
    result,trace=run();self.assertEqual(result,[]);self.assertEqual(trace['status'],'failed');self.assertIsNone(trace['candidate_count'])
   self.assertEqual(self.store.search_calls-before,1)
   receipts.append({'fault_injection':cls.__name__,'trace':trace,'search_calls':1})
  text=(logdir/'app.log').read_text(encoding='utf-8');(r/'consumer-final.log').write_text(text,encoding='utf-8')
  self.assertIn(SENTINEL,text);self.assertNotIn(KEY,text)
  (r/'consumer-receipt.json').write_text(json.dumps({'source_hashes':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,logpath,repo/'backend/source_control.py',repo/'backend/evidence_trace.py']},'functions':sorted(names),'receipts':receipts,'final_log_bare_marker_present':SENTINEL in text,'api_key_value_redacted':KEY not in text,'not_run':['full_worker','full_API','provider_models']},indent=2))
if __name__=='__main__':unittest.main(verbosity=2)




