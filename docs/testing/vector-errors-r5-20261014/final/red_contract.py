import json, pathlib, traceback
from generic_filter import StaticProjection
r=pathlib.Path(__file__).parent
fail=[]
for name, action, code in [
 ('filter', lambda:StaticProjection([{'id':'x','metadata':{'a':1}}]).compile({'a':{'$in':[]}}),'invalid_filter'),
 ('mixed_keys',lambda:StaticProjection([{'id':'x','metadata':{'a':1,2:3}}]),'invalid_input'),
 ('record',lambda:StaticProjection([{'id':'x','metadata':{'a':1}}]).encode({'id':'x','metadata':{'a':2**64}}),'invalid_input'),
]:
 try:
  action(); raise AssertionError('did not reject')
 except Exception as e:
  if getattr(e,'code',None)!=code:fail.append({'case':name,'class':type(e).__name__,'expected':code,'actual':getattr(e,'code',None)})
(r/'red-contract.json').write_text(json.dumps(fail,indent=2))
print(json.dumps(fail)); raise SystemExit(bool(fail))
