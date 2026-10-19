import pathlib,hashlib,json,shutil
p=pathlib.Path('docs/testing/sqlite-vector-r8-20261017');out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017/adapter')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(p/'manifest.json')=='ff9d60f7e90477debc95f93781aaf8e239452069ccd328c75e704d78c321506a'
m=json.loads((p/'manifest.json').read_text());assert len(m)==37
for f,v in m.items(): assert h(p/f)==v['sha256'],f
shutil.copytree(p/'backend',out/'backend');shutil.copytree(p/'tests',out/'tests')
print('adapter37 verified and copied')
