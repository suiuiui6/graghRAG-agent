"""Hash-only protected production assets, with no private body/name export."""
from pathlib import Path
import argparse
import hashlib
import json

SCOPES=('backend/output/kg','backend/output/runtime','backend/output/vectordb',
        'backend/output/embedding_cache','backend/output/lineage','backend/output/conversations',
        'backend/output/docs_store.json','backend/output/rewrite-cache.sqlite3')

def snapshot(repo):
    files={}
    for scope in SCOPES:
        p=repo/scope
        for f in ([p] if p.is_file() else sorted(p.rglob('*')) if p.exists() else []):
            if not f.is_file():continue
            name=hashlib.sha256(f.relative_to(repo).as_posix().encode()).hexdigest()
            files[name]={'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    return {'scope':SCOPES,'label_handling':'Hashed relative names; bodies not exported',
            'files':files,'file_count':len(files),'bytes':sum(f['bytes'] for f in files.values())}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--compare',type=Path)
    a=p.parse_args();result=snapshot(a.repo.resolve())
    if a.compare:
        before=json.loads(a.compare.read_text(encoding='utf-8'))
        result['unchanged']=before['files']==result['files']
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('file_count','bytes','unchanged') if k in result}))
    if result.get('unchanged') is False:raise SystemExit(1)
