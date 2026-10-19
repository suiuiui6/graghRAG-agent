import pathlib,hashlib,json,shutil
p=pathlib.Path('docs/testing/sqlite-vector-r8-r2-20261017');out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017/adapter-r2');h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(p/'manifest.json')=='9d4e97242ea1e536669502ab28d16a9b5beaa0dff6ce410d1726666293761cc7';m=json.loads((p/'manifest.json').read_text());assert len(m)==42
for f,v in m.items():assert h(p/f)==v['sha256'],f
shutil.copytree(p/'backend',out/'backend');shutil.copytree(p/'tests',out/'tests');shutil.copy('.tmp/sqlite-r8-r2-review-20261017/adapter/tests/test_review_core.py',out/'tests/test_review_core.py');print('42hash verified and copied')
