import sys, sqlite3, json, hashlib, importlib.metadata as md, pathlib, datetime
out=pathlib.Path('.tmp/vector-native-audit-20261014')
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
c=sqlite3.connect(':memory:')
r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'base_prefix':sys.base_prefix,'sqlite_version':sqlite3.sqlite_version,'sqlite_threadsafety':sqlite3.threadsafety,'sqlite_compile_options':[x[0] for x in c.execute('pragma compile_options')], 'sqlite_source_id':c.execute('select sqlite_source_id()').fetchone()[0], 'defensive_constant':getattr(sqlite3,'SQLITE_DBCONFIG_DEFENSIVE',None)}
try:
 r['defensive_initial']=c.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE)
 c.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE,True)
 r['defensive_enabled']=c.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE)
except Exception as e:r['defensive_error']=type(e).__name__
r['trusted_schema_initial']=c.execute('pragma trusted_schema').fetchone()[0]
r['packages']={}
for name in ['lancedb','pyarrow','numpy','pydantic-core']:
 d=md.distribution(name); native=[]; sbom=[]
 for f in d.files or []:
  p=pathlib.Path(d.locate_file(f)); s=str(f)
  if p.is_file() and (p.suffix.lower() in ['.dll','.pyd']):native.append({'path':s,'sha256':h(p),'size':p.stat().st_size})
  if any(x in s.lower() for x in ['sbom','spdx','cyclonedx','cargo.lock']):sbom.append(s)
 r['packages'][name]={'version':d.version,'wheel':d.read_text('WHEEL'),'native':native,'sbom_candidates':sbom}
import pyarrow as pa, numpy as np, lancedb
r['arrow_cpp_build_info']=str(pa.cpp_build_info)
r['arrow_runtime_info']=str(pa.runtime_info())
r['lancedb_version']=lancedb.__version__
r['numpy_config']=np.show_config(mode='dicts')
p=out/'runtime-native.json';p.write_text(json.dumps(r,indent=2,default=str),encoding='utf-8')
print(json.dumps({'python':sys.version.split()[0],'sqlite':r['sqlite_version'],'defensive_initial':r.get('defensive_initial'),'defensive_enabled':r.get('defensive_enabled'),'native_counts':{k:len(v['native']) for k,v in r['packages'].items()},'sbom':{k:v['sbom_candidates'] for k,v in r['packages'].items()}},indent=2))
