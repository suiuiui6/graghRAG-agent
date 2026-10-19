import pathlib,subprocess,json,hashlib
p=pathlib.Path('.tmp/vector-native-audit-20261014/tooling'); db=p/'db-fixed'
cmd=['git','-C',str(db),'archive','--format=tar','HEAD']
with (p/'rustsec-db.tar').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE)
commit=subprocess.check_output(['git','-C',str(db),'rev-parse','HEAD'],text=True).strip()
time=subprocess.check_output(['git','-C',str(db),'show','-s','--format=%cI','HEAD'],text=True).strip()
rec={'source':'https://github.com/RustSec/advisory-db.git','commit':commit,'commit_time':time,'archive_sha256':hashlib.sha256((p/'rustsec-db.tar').read_bytes()).hexdigest(),'archive_exit':r.returncode,'advisory_files':len(list((db/'crates').glob('**/*.md')))}
(p/'db-receipt.json').write_text(json.dumps(rec,indent=2),encoding='utf8');print(rec)
