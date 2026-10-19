"""Isolated pre-render processor: fixed identities, no exception formatting."""
import sys,types
from vector_errors import VectorStoreError,VectorInputError,VectorStorageError,VectorCapabilityError,MESSAGES,OPERATIONS
_FRAMES={}
_TYPES={ValueError:'ValueError',TypeError:'TypeError',OSError:'OSError',RuntimeError:'RuntimeError',Exception:'Exception',VectorStoreError:'VectorStoreError',VectorInputError:'VectorInputError',VectorStorageError:'VectorStorageError',VectorCapabilityError:'VectorCapabilityError'}
_TYPED=(VectorStoreError,VectorInputError,VectorStorageError,VectorCapabilityError)
def register(code,file,function):
 if type(code) is not types.CodeType or type(file) is not str or type(function) is not str:raise TypeError('invalid static registration')
 _FRAMES[id(code)]=(code,file,function)
def processor(logger,method,event):
 value=event.get('exc_info')
 if value is True:value=sys.exc_info()
 exc=value[1] if type(value) is tuple and len(value)==3 else value if isinstance(value,BaseException) else None
 if not isinstance(exc,BaseException):return event
 queue=[(exc,'root')];seen=set();nodes=[];frames=[];cycle=False;typed=None
 while queue and len(nodes)<32:
  current,relation=queue.pop(0)
  if id(current) in seen:cycle=True;continue
  seen.add(id(current));cls=type(current)
  if any(cls is t for t in _TYPED) and typed is None:typed=current
  nodes.append({'type':next((label for t,label in _TYPES.items() if cls is t),'Exception'),'relation':relation})
  tb=BaseException.__traceback__.__get__(current)
  while tb is not None and len(frames)<32:
   code=tb.tb_frame.f_code;entry=_FRAMES.get(id(code));label=entry[1:] if entry is not None and entry[0] is code else ('unknown_frame','unknown_frame')
   line=tb.tb_lineno;frames.append({'file':label[0],'function':label[1],'line':line if type(line) is int else 0});tb=tb.tb_next
  for name in ('__cause__','__context__'):
   linked=vars(BaseException)[name].__get__(current)
   if linked is not None:queue.append((linked,'cause' if name=='__cause__' else 'context'))
 # A chain can hide a typed error beyond diagnostic budget. A separate bounded discovery
 # pass makes this visible without rendering arbitrary exception values.
 if typed is None and queue:
  todo=list(queue);discovered=set(seen)
  for _ in range(512):
   if not todo:break
   current,_=todo.pop(0)
   if id(current) in discovered:continue
   discovered.add(id(current))
   if any(type(current) is t for t in _TYPED):typed=current;break
   for name in ('__cause__','__context__'):
    linked=vars(BaseException)[name].__get__(current)
    if linked is not None:todo.append((linked,'cause'))
 # Exhausted discovery with unresolved tail fails closed; this also protects
 # wrappers hiding a typed cause beyond the bounded discovery budget.
 if typed is None and not queue:return event
 attrs=BaseException.__dict__['__dict__'].__get__(typed) if typed is not None else {}
 code=attrs.get('code');operation=attrs.get('operation')
 code=code if type(code) is str and code in MESSAGES else 'unknown'
 operation=operation if type(operation) is str and operation in OPERATIONS else 'unknown'
 out={'event':'vector_store_failure','level':'error','vector_error':{'code':code,'operation':operation,'retryable':False,'chain':nodes,'frames':frames,'cycle':cycle,'truncated':bool(queue) or len(frames)>=32}}
 status=event.get('status');count=event.get('candidate_count')
 if type(status) is str and status in ('failed','executed'):out['status']=status
 if count is None or type(count) is int and 0<=count<=1000000:out['candidate_count']=count
 return out
