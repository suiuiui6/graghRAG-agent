import pathlib,json,hashlib,importlib.metadata as md
out=pathlib.Path('.tmp/vector-native-audit-20261014')
r={}
for n in ['lancedb','pydantic-core']:
 d=md.distribution(n)
 for f in d.files:
  if 'cyclonedx' in str(f):
   p=pathlib.Path(d.locate_file(f)); raw=p.read_bytes(); target=out/(n+'-sbom.json');target.write_bytes(raw);s=json.loads(raw)
   r[n]={'sha256':hashlib.sha256(raw).hexdigest(),'components':len(s.get('components',[])),'metadata':s.get('metadata',{}),'selected':[x for x in s.get('components',[]) if any(y in x.get('name','').lower() for y in ['arrow','lance','sqlite','openssl','zstd','lz4','parquet','tokio','datafusion'])]}
(out/'sbom-summary.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps(r,indent=2)[:14000])
