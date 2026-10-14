import pathlib,json,hashlib,shutil,sys
r=pathlib.Path(__file__).resolve().parent
repo=r.parents[1]
src=repo/'docs/testing/vector-errors-r5-20261014'
m=json.loads((src/'r5-freeze-manifest.json').read_text())
dst=r/(sys.argv[1] if len(sys.argv)>1 else 'snapshot');dst.mkdir(exist_ok=True)
for name,digest in m['files'].items():
 p=src/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
 q=dst/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
old=repo/'docs/testing/vector-ingress-r4b-20261014'
om=json.loads((old/'freeze-manifest.json').read_text())
for name,digest in om['files'].items():assert hashlib.sha256((old/name).read_bytes()).hexdigest()==digest,name
(r/(dst.name+'-receipt.json')).write_text(json.dumps({'r5_count':len(m['files']),'r4b_count':len(om['files']),'r5_manifest_sha256':hashlib.sha256((src/'r5-freeze-manifest.json').read_bytes()).hexdigest()},indent=2))
print('VERIFIED',len(m['files']),len(om['files']))
