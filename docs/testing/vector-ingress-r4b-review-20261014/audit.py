import hashlib, importlib.util, json, math, random, struct, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
repo=Path(__file__).resolve().parents[2]
root=repo/'docs/testing/vector-ingress-r4b-20261014'
out=Path(__file__).resolve().parent
manifest=json.loads((root/'freeze-manifest.json').read_text())
bad=[p for p,h in manifest['files'].items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
assert len(manifest['files'])==110 and not bad, bad
old=repo/'docs/testing/vector-ingress-r4-20261014'
oldmanifest=json.loads((old/'freeze-manifest.json').read_text())
oldbad=[p for p,h in oldmanifest['files'].items() if hashlib.sha256((old/p).read_bytes()).hexdigest()!=h]
assert not oldbad,oldbad
spec=importlib.util.spec_from_file_location('port',root/'parser_port.py')
port=importlib.util.module_from_spec(spec);spec.loader.exec_module(port)
rng=random.Random(202610141731)
tokens=['-0','0','-0.0','0.0',str(2**63),str(2**64-1),str(2**64),str(-2**63-1),'1e309','-1e309']
bits=[]
while len(bits)<4096:
    n=rng.getrandbits(64); v=struct.unpack('>d',n.to_bytes(8,'big'))[0]
    if math.isfinite(v):bits.append(n);tokens.append(json.dumps(v))
for _ in range(1024):
    n=rng.getrandbits(rng.randint(1,1100));tokens.append(str(n if rng.randrange(2) else -n))
helper=repo/'.tmp/vector-ingress-debug-20261014/target/debug/ingress-oracle.exe'
inputs=tokens+['bits:'+format(n,'016x') for n in bits]
result=subprocess.run([str(helper)],input='\n'.join(inputs)+'\n',text=True,capture_output=True,timeout=60)
assert result.returncode==0,result.stderr
lines=[json.loads(line) for line in result.stdout.splitlines()]
assert len(lines)==len(inputs)
diff=[]
for i,truth in enumerate(lines):
    try:
        tag,v=port.parse(truth['token'])
        actual={'float':tag=='f64','i64':v if tag=='i64' or tag=='u64' and v<2**63 else None,'u64':v if tag=='u64' or tag=='i64' and v>=0 else None,'f64_bits':struct.pack('>d',float(v)).hex()}
        if 'error' in truth or any(truth[k]!=v for k,v in actual.items()):diff.append({'index':i,'truth':truth,'actual':actual})
    except ValueError as exc:
        if 'error' not in truth:diff.append({'index':i,'truth':truth,'actual_error':str(exc)})
receipt={'utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':hashlib.sha256((root/'freeze-manifest.json').read_bytes()).hexdigest(),'frozen_files_verified':len(manifest['files']),'old_r4_files_verified':len(oldmanifest['files']),'parser_sha256':hashlib.sha256((root/'parser_port.py').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'seed':202610141731,'parser_differentials':len(lines),'float_query_samples':4096,'float_record_samples':4096,'integer_samples':1024,'boundary_samples':10,'differences':diff,'helper_exit_code':result.returncode}
(out/'audit-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
assert not diff
