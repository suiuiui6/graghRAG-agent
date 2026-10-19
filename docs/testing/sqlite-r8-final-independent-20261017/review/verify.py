import pathlib, hashlib, json, shutil
root=pathlib.Path('docs/testing/sqlite-r8-consumers-r2-20261017')
out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(root/'manifest.json')=='63d4084f6ad92d6df1e80c3132e1ff9ac9ff385f9d392df20eb64d4ae8206f8d'
m=json.loads((root/'manifest.json').read_text())
assert len(m)==66
for f,v in m.items(): assert h(root/f)==v, f
shutil.copytree(root/'source',out/'source')
for f,v in m.items():
 if f.startswith('source/'): assert h(out/f)==v, f
(out/'verified.json').write_text(json.dumps({'manifest_sha256':h(root/'manifest.json'),'count':len(m),'hashes':m},indent=2))
print('66 frozen hashes verified and source copied')
