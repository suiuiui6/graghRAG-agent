import pathlib,json,hashlib,zipfile,subprocess
p=pathlib.Path('.tmp/vector-native-audit-20261014/tooling');a=p/'cargo-audit-0.22.2-api.zip';r=json.loads((p/'release.json').read_text(encoding='utf-8-sig'));asset=next(x for x in r['assets'] if 'windows' in x['name']);digest=hashlib.sha256(a.read_bytes()).hexdigest();assert 'sha256:'+digest==asset['digest'];b=p/'bin';b.mkdir(exist_ok=True)
with zipfile.ZipFile(a) as z:
 for n in z.namelist():
  target=(b/n).resolve();assert target.is_relative_to(b.resolve()),n
 z.extractall(b)
exe=next(b.glob('**/cargo-audit.exe'))
r={'release_tag':'cargo-audit/v0.22.2','asset_id':asset['id'],'asset_sha256':digest,'official_digest_verified':True,'exe':str(exe),'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
(p/'tool-receipt.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(r)
