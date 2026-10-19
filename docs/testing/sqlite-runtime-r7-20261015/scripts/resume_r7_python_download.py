import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-runtime-r7-20261015'
release=json.loads((out/'release.json').read_text(encoding='utf-8'))
name='cpython-3.12.15+20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
asset=next(x for x in release['assets'] if x['name']==name)
expected=asset['digest'].removeprefix('sha256:')
target=out/'python.tar.gz'
cmd=['curl.exe','--fail','--location','--max-time','300','--retry','0','--continue-at','-','--output',str(target),asset['browser_download_url']]
with (out/'resume-download.log').open('w',encoding='utf-8') as log:
    run=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
(out/'resume-download.exit').write_text(str(run.returncode),encoding='utf-8')
assert run.returncode==0,run.returncode
actual=hashlib.sha256(target.read_bytes()).hexdigest()
assert actual==expected and target.stat().st_size==asset['size']
dest=out/'runtime';assert not dest.exists()
with tarfile.open(target,'r:gz') as archive:
    # The official hash is checked before extraction; reject path traversal/links.
    for member in archive.getmembers():
        p=(dest/member.name).resolve();assert p.is_relative_to(dest.resolve())
        assert not member.issym() and not member.islnk()
    archive.extractall(dest,filter='data')
receipt={'release':release['tag_name'],'asset_id':asset['id'],'asset_name':name,'url':asset['browser_download_url'],'bytes':asset['size'],'sha256':actual,'official_digest':asset['digest'],'download_exit':run.returncode,'runtime':str(dest)}
(out/'artifact-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
