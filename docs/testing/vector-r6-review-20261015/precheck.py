import json, pathlib, sys
if len(sys.argv)>1:sys.path.insert(0,str(pathlib.Path(sys.argv[1]).resolve()))
import safe_vector_logging as s
from vector_errors import VectorStorageError
MARK='INDEPENDENT_R6_PRIVATE_84015'
calls=[]
class Meta(type):
 def __getattribute__(self,key):
  calls.append('meta:'+key); raise AssertionError('meta access')
class Sub(VectorStorageError,metaclass=Meta):
 def __getattribute__(self,key):
  calls.append('exc:'+key);raise AssertionError('exc access')
 def __str__(self):
  calls.append('str');raise AssertionError('str')
 def __repr__(self):
  calls.append('repr');raise AssertionError('repr')
e=BaseException.__new__(Sub)
BaseException.__dict__['__dict__'].__get__(e).update(code='storage_unavailable',operation='search')
cause=RuntimeError(MARK)
BaseException.__cause__.__set__(e,cause)
event={'event':MARK,'exc_info':e,'extra':MARK}
out=s.processor(None,'error',event)
ordinary=RuntimeError(MARK)
for i in range(40):
 parent=RuntimeError(MARK);parent.__cause__=ordinary;ordinary=parent
longout=s.processor(None,'error',{'event':MARK,'exc_info':ordinary})
result={'typed_subclass_sanitized':out is not event and 'exc_info' not in out,'user_code_calls':calls,'original_cause_preserved':BaseException.__cause__.__get__(e) is cause,'ordinary_long_chain_rewritten':longout.get('event')=='vector_store_failure'}
pathlib.Path(__file__).with_name('precheck-final.json' if len(sys.argv)>1 else 'precheck.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result));assert result['typed_subclass_sanitized']
