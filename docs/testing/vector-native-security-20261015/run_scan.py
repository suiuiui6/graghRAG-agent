import pathlib,subprocess,json,os,hashlib,datetime,time
p=pathlib.Path('.tmp/vector-native-audit-20261014/tooling').resolve();r=json.loads((p/'tool-receipt.json').read_text(encoding='utf8'));exe=pathlib.Path(r['exe']).resolve();env=os.environ.copy();env['CARGO_HOME']=str(p/'cargo-home');env['CARGO_TARGET_DIR']=str(p/'cargo-target');results=[]
for name in ['lancedb','pydantic-core']:
 cmd=[str(exe),'audit','--file',str(p/(name+'.inventory.lock')),'--db',str(p/'db-fixed'),'--no-fetch','--no-yanked','--json','--deny','warnings']
 t=time.monotonic();rr=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=p,timeout=90)
 (p/(name+'.audit.json')).write_bytes(rr.stdout);(p/(name+'.audit.log')).write_bytes(rr.stderr);(p/(name+'.audit.exit')).write_text(str(rr.returncode)+'\n',encoding='ascii');results.append({'name':name,'command':cmd,'exit':rr.returncode,'seconds':time.monotonic()-t})
 print(name,'exit',rr.returncode,rr.stderr.decode('utf8',errors='replace')[:900]);
 if rr.stdout:
  d=json.loads(rr.stdout);print('keys',list(d));print('vulnerabilities',d.get('vulnerabilities',{}).get('count'),'warnings',{k:len(v) for k,v in d.get('warnings',{}).items()})
(p/'scan-receipt.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,'scope':'SBOM synthetic version inventory, not actual Cargo graph; no target filter; yanked registry lookup intentionally NOT_RUN to keep fixed offline DB audit'},indent=2),encoding='utf8')
