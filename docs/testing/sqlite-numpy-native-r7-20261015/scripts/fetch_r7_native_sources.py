import datetime,hashlib,json,urllib.error,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-numpy-native-audit-20261015';out.mkdir(exist_ok=True)
sources={
 'numpy-pypi.json':'https://pypi.org/pypi/numpy/2.5.4/json',
 'openblas-build-pypi.json':'https://pypi.org/pypi/scipy-openblas64/0.3.34.106.0/json',
 'openblas-security.txt':'https://raw.githubusercontent.com/OpenMathLib/OpenBLAS/develop/SECURITY.md',
}
receipts=[]
for name,url in sources.items():
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'GraphRAG-isolated-runtime-audit'})
        with urllib.request.urlopen(req,timeout=45) as response:
            body=response.read(2_000_001);assert len(body)<=2_000_000
            status=response.status
        (out/name).write_bytes(body)
        receipts.append({'file':name,'url':url,'status':status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
    except Exception as exc:
        receipts.append({'file':name,'url':url,'error_type':type(exc).__name__,'status':getattr(exc,'code',None)})
(out/'sources-receipt.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':receipts},indent=2),encoding='utf-8')
print(json.dumps(receipts))
raise SystemExit(any('error_type' in x for x in receipts))
