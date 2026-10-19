import pathlib,json,hashlib
p=pathlib.Path('.tmp/vector-native-audit-20261014');o=p/'tooling';r={}
for name in ['lancedb','pydantic-core']:
 raw=(p/(name+'-sbom.json')).read_bytes();s=json.loads(raw)
 packages={};non_registry=[]
 for c in s['components']:
  assert c.get('purl','').startswith('pkg:cargo/'), c
  key=(c['name'],c['version'])
  assert key not in packages,key
  packages[key]=c
  if not c['bom-ref'].startswith('registry+'):non_registry.append({'name':c['name'],'version':c['version'],'purl':c['purl']})
 lines=['# SYNTHETIC SBOM VERSION INVENTORY: NOT AN ACTUAL CARGO RESOLUTION', '# No dependency graph, feature or platform reachability is represented.', 'version = 4','']
 for (n,v),c in sorted(packages.items()):
  lines += ['[[package]]','name = '+json.dumps(n),'version = '+json.dumps(v)]
  if c['bom-ref'].startswith('registry+'):
   assert c['bom-ref'].startswith('registry+https://github.com/rust-lang/crates.io-index#'),c
   lines += ['source = "registry+https://github.com/rust-lang/crates.io-index"']
   hashes=[h['content'] for h in c.get('hashes',[]) if h['alg']=='SHA-256']
   assert len(hashes)==1,c
   lines += ['checksum = '+json.dumps(hashes[0])]
  lines += ['']
 target=o/(name+'.inventory.lock');target.write_text('\n'.join(lines),encoding='utf8')
 r[name]={'sbom_sha256':hashlib.sha256(raw).hexdigest(),'components':len(packages),'registry':len(packages)-len(non_registry),'non_registry':non_registry,'inventory_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'synthetic':True,'scope':'SBOM all-targets package name/version inventory only; no graph/features/Windows reachability'}
(o/'inventory-receipt.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r,indent=2))
