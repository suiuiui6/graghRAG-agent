import random,struct,math,json,subprocess,hashlib
from pathlib import Path
from parser_port import parse
r=Path(__file__).resolve().parent
rng=random.Random(20261014); vals=[]
while len(vals)<12000:
 b=rng.getrandbits(64); f=struct.unpack('>d',b.to_bytes(8,'big'))[0]
 if math.isfinite(f):vals.append((b,f))
inputs=[json.dumps(f) for b,f in vals]+['bits:'+format(b,'016x') for b,f in vals]+[str(i) for i in [-(1<<63)-1,1<<63,-(1<<64),1<<64,0,-1]]+['-0','-0.0']
proc=subprocess.run([str(r/'target/debug/ingress-oracle.exe')],input='\n'.join(inputs)+'\n',capture_output=True,text=True,check=True)
rows=[json.loads(s) for s in proc.stdout.splitlines()];bad=[]
for input_,row in zip(inputs,rows):
 try:
  tag,v=parse(row['token']);bits=struct.pack('>d',float(v)).hex()
  if bits!=row.get('f64_bits') or (tag=='f64')!=row.get('float'):bad.append({'input':input_,'row':row,'port':[tag,str(v),bits]})
 except ValueError:
  if 'error' not in row:bad.append({'input':input_,'row':row,'port':'error'})
(r/'independent-inputs.txt').write_text('\n'.join(inputs)+'\n',encoding='ascii')
(r/'helper-oracle.jsonl').write_text(proc.stdout,encoding='ascii')
report={'seed':20261014,'random_finite_values':len(vals),'cases':len(inputs),'differences':bad,'input_sha256':hashlib.sha256((r/'independent-inputs.txt').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256((r/'target/debug/ingress-oracle.exe').read_bytes()).hexdigest()}
(r/'port-differential.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(inputs),'differences':len(bad)}))
raise SystemExit(bool(bad))
