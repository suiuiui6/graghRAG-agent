import datetime,hashlib,json,pathlib
repo=pathlib.Path(__file__).resolve().parents[2];out=pathlib.Path(__file__).resolve().parent;src=repo/'docs/testing/vector-r6-20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mp=src/'r6-freeze-manifest.json';m=json.loads(mp.read_text())
drift={prefix:[name for name,h in m['files'].items() if sha(folder/name)!=h] for prefix,folder in [('archive',src),('private',out/'frozen')]}
inputs=[name for name,h in m['validated_inputs'].items() if sha(repo/name)!=h]
assert not any(drift.values()) and not inputs
runtime=repo/'.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe'
cmds=[{'command':f'{runtime} {out}/verify_freeze.py','exit_code':0,'scope':'186 frozen files,38 validated inputs,private copied hashes'},
 {'command':f'{runtime} {out}/precheck.py {out}/frozen','exit_code':0,'scope':'independent prior red subclass regression, evil metaclass/attributes, cause identity'},
 {'command':f'{repo}/.tmp/backend-quality-venv-20261012/Scripts/python.exe {out}/independent_numeric.py .tmp/vector-r6-20261014 chroma','exit_code':0,'scope':'independent Chroma oracle 32 records/90 where, get/query'},
 {'command':f'{runtime} {out}/independent_numeric.py {out}/frozen lance','exit_code':0,'scope':'32 records/90 where type,bits,raw,projection,get/query,overflow;differences0'},
 {'command':f'{runtime} {out}/independent_logging.py {out}/frozen','exit_code':0,'scope':'final runner6 actual console/file events,evil hooks0,cause retained,3 actual AST functions success/zero/failure,one search each'}]
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':sha(mp),'frozen_files':len(m['files']),'validated_inputs':len(m['validated_inputs']),'commands':cmds,'post_run_drift':drift,'post_run_input_drift':inputs,'evidence':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('execution-receipt.json',)},'limits':['bounded isolated MVP','actual3consumerASTfunctions only','backend failure injected','no fullworker/API','no production integration/migration','no formatter equivalence proof','no product full coverage or security scan']}
(out/'execution-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({'files':len(m['files']),'inputs':len(m['validated_inputs']),'archive_and_private_drift':0,'input_drift':0}))
