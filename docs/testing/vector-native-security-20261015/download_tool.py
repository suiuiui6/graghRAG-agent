import subprocess,pathlib,time,json
p=pathlib.Path('.tmp/vector-native-audit-20261014/tooling');t=time.monotonic()
cmd=['gh','api','-H','Accept: application/octet-stream','repos/rustsec/rustsec/releases/assets/439294720']
with (p/'cargo-audit-0.22.2-api.zip').open('wb') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE,timeout=90);code=r.returncode;err=r.stderr.decode('utf8',errors='replace')
 except subprocess.TimeoutExpired:code=124;err='bounded download timeout (90 seconds)'
(p/'download-api-receipt.json').write_text(json.dumps({'command':cmd,'exit':code,'seconds':time.monotonic()-t,'stderr':err},indent=2),encoding='utf8');print(code,err)
