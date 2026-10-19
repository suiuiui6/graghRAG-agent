import csv,hashlib,io,json,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-runtime-r7-20261015/sqlite-official';out.mkdir(exist_ok=True)
with urllib.request.urlopen('https://sqlite.org/download.html',timeout=30) as response:page=response.read()
(out/'download.html').write_bytes(page)
rows=[next(csv.reader([line])) for line in page.decode().splitlines() if line.startswith('PRODUCT,')]
row=next(x for x in rows if x[2].endswith('/sqlite-dll-win-x64-3540000.zip'))
expected='f5fb500c73a3afd89976386bb8e4fdc8b5b65c052e187fb1ada1f5de034cd45b'
assert row[4]==expected
url='https://sqlite.org/'+row[2]
with urllib.request.urlopen(url,timeout=60) as response:data=response.read(5_000_001)
assert len(data)<=5_000_000 and len(data)==int(row[3])
assert hashlib.sha3_256(data).hexdigest()==expected
(out/'sqlite-dll-win-x64-3540000.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    assert archive.namelist().count('sqlite3.dll')==1
    dll=archive.read('sqlite3.dll')
(out/'sqlite3.dll').write_bytes(dll)
receipt={'download_page_url':'https://sqlite.org/download.html','download_page_sha256':hashlib.sha256(page).hexdigest(),'url':url,'version':row[1],'bytes':len(data),'official_sha3_256':expected,'actual_sha3_256':hashlib.sha3_256(data).hexdigest(),'archive_sha256':hashlib.sha256(data).hexdigest(),'dll_sha256':hashlib.sha256(dll).hexdigest(),'extracted_members':['sqlite3.dll'],'executed':False}
(out/'sqlite-artifact-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
