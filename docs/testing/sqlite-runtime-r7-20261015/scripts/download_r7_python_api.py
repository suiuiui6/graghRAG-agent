import hashlib,json,subprocess,tarfile,time
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-runtime-r7-20261015'
release=json.loads((out/'release.json').read_text(encoding='utf-8'))
name='cpython-3.12.15+20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
asset=next(x for x in release['assets'] if x['name']==name)
dest=out/'runtime';assert not dest.exists()
target=out/'python-api.tar.gz'
command=['gh','api','-H','Accept: application/octet-stream',f"repos/astral-sh/python-build-standalone/releases/assets/{asset['id']}"]
started=time.monotonic()
with target.open('wb') as f:
    try:
        result=subprocess.run(command,stdout=f,stderr=subprocess.PIPE,timeout=180)
        code=result.returncode;error=result.stderr.decode('utf-8',errors='replace')
    except subprocess.TimeoutExpired:
        code=124;error='bounded official asset API download timeout'
receipt={'command':command,'seconds':time.monotonic()-started,'exit_code':code,'stderr':error,'release':release['tag_name'],'asset_name':name,'asset_id':asset['id'],'url':asset['browser_download_url'],'official_digest':asset['digest'],'bytes':target.stat().st_size,'prior_direct_download':'first timeout28; resume manually interrupted due persistently low transfer rate, unexecuted partial preserved'}
(out/'api-download-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
assert code==0,code
actual=hashlib.sha256(target.read_bytes()).hexdigest()
assert actual==asset['digest'].removeprefix('sha256:') and target.stat().st_size==asset['size']
with tarfile.open(target,'r:gz') as archive:
    for member in archive.getmembers():
        assert (dest/member.name).resolve().is_relative_to(dest.resolve())
        assert not member.issym() and not member.islnk()
    archive.extractall(dest,filter='data')
receipt.update({'sha256':actual,'digest_verified':True,'runtime':str(dest)})
(out/'artifact-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'exit':code,'sha256':actual,'bytes':target.stat().st_size,'runtime':str(dest)}))
