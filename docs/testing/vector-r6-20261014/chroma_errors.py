import chromadb,hashlib,importlib.metadata,json,pathlib,tempfile,sys
r=pathlib.Path(__file__).resolve().parent
client=chromadb.PersistentClient(path=tempfile.mkdtemp(prefix='real-chroma-',dir=r)); c=client.get_or_create_collection('r5-probe',metadata={'hnsw:space':'cosine'})
c.add(ids=['a'],embeddings=[[1.,0.,0.]],metadatas=[{'n':1}],documents=['synthetic'])
results=[]
def case(name,code,fn):
 try:
  value=fn();result={'name':name,'status':'OK','value':value}
  if code:raise AssertionError(name+' accepted')
 except AssertionError:raise
 except Exception as e:
  if not code:raise
  result={'name':name,'status':'REJECTED','application_category':code,'native_class':type(e).__module__+'.'+type(e).__name__,'native_message':str(e)}
 results.append(result)
case('valid',None,lambda:c.query(query_embeddings=[[1.,0.,0.]],n_results=1)['ids'])
case('no_match',None,lambda:c.get(where={'n':99})['ids'])
for name,where in [('empty_set',{'n':{'$in':[]}}),('mixed_set',{'n':{'$in':[1,'x']}}),('u64',{'n':2**63}),('numeric_overflow',{'n':10**400})]:case(name,'invalid_filter',lambda where=where:c.get(where=where))
case('dimension','invalid_dimension',lambda:c.query(query_embeddings=[[1.,0.]],n_results=1))
case('length','invalid_input',lambda:c.add(ids=['b','c'],embeddings=[[1.,0.,0.]]))
case('record_overflow_native',None,lambda:c.add(ids=['d'],embeddings=[[1.,0.,0.]],metadatas=[{'n':2**64}]))
results[-1]['candidate_policy']='invalid_input: signed-I64 record domain; native acceptance observed'
case('record_invalid','invalid_input',lambda:c.add(ids=['e'],embeddings=[[1.,0.,0.]],metadatas=[{'n':{'nested':1}}]))
# Chroma may accept nonfinite; record its actual behavior without false normalization.
try:
 value=c.query(query_embeddings=[[float('nan'),0.,0.]],n_results=1);results.append({'name':'nonfinite','status':'NATIVE_ACCEPTED','ids':value['ids'],'candidate_policy':'invalid_input'})
except Exception as e:results.append({'name':'nonfinite','status':'REJECTED','native_class':type(e).__name__,'candidate_policy':'invalid_input'})
bad=r/'chroma-ordinary-file';bad.write_text('synthetic')
case('real_bad_path','storage_unavailable',lambda:chromadb.PersistentClient(path=str(bad)))
for index,number in enumerate([2**63,2**64,-2**63-1]):
 try:
  ident='wide-'+str(index);c.add(ids=[ident],embeddings=[[1.,0.,0.]],metadatas=[{'n':number}]);readback=c.get(ids=[ident])['metadatas'][0]['n'];results.append({'name':'record_wide_readback','input':number,'status':'NATIVE_ACCEPTED','readback':readback,'readback_type':type(readback).__name__,'float_hex':readback.hex() if type(readback) is float else None,'candidate_policy':'REJECTED invalid_input; compatibility GAP'})
 except Exception as e:results.append({'name':'record_wide_readback','input':number,'status':'REJECTED','native_class':type(e).__name__,'native_message':str(e)})
(r/'chroma-errors.json').write_text(json.dumps({'version':chromadb.__version__,'python':sys.version,'cases':results,'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},indent=2))
print(json.dumps({'cases':len(results),'status':'PASS'}))


