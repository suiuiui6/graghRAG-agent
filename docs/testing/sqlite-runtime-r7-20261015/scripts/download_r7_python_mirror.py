import hashlib,json,subprocess,tarfile,time
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-runtime-r7-20261015'
release=json.loads((out/'release.json').read_text(encoding='utf-8'))
name='cpython-3.12.15+20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
asset=next(x for x in release['assets'] if x['name']==name)
target=out/'python-mirror.tar.gz';dest=out/'runtime';assert not dest.exists()
url='https://registry.npmmirror.com/-/binary/python-build-standalone/20261013/'+name.replace('+','%2B')
command=['curl.exe','--fail','--location','--max-time','90','--retry','0','--output',str(target),url]
start=time.monotonic()
with (out/'mirror-download.log').open('w',encoding='utf-8') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
receipt={'command':command,'exit_code':result.returncode,'seconds':time.monotonic()-start,'transport':'third-party mirror; never trusted as provenance','official_url':asset['browser_download_url'],'official_asset_id':asset['id'],'official_digest':asset['digest'],'release':release['tag_name'],'bytes':target.stat().st_size if target.exists() else 0}
(out/'mirror-download-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
assert result.returncode==0,result.returncode
digest=hashlib.sha256(target.read_bytes()).hexdigest()
assert digest==asset['digest'].removeprefix('sha256:') and target.stat().st_size==asset['size']
with tarfile.open(target,'r:gz') as archive:
    for member in archive.getmembers():
        assert (dest/member.name).resolve().is_relative_to(dest.resolve())
        assert not member.issym() and not member.islnk()
    archive.extractall(dest,filter='data')
receipt.update({'sha256':digest,'digest_verified':True,'runtime':str(dest),'prior_attempts':'direct timeout28; slow direct resume manually interrupted; official API bounded attempt logged separately. All partials retained and unexecuted.'})
(out/'artifact-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'exit':result.returncode,'bytes':target.stat().st_size,'sha256':digest,'runtime':str(dest)}))
