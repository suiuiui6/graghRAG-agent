from pathlib import Path
import hashlib, json, shutil, subprocess, datetime
root=Path('D:/graghRAG-agent')
old=root/'docs/testing/sqlite-r8-consumers-20261016'
work=root/'.tmp/sqlite-r8-consumers-20261016'
dest=root/'docs/testing/sqlite-r8-consumers-r2-20261017'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=json.loads((old/'manifest.json').read_text())
assert all(sha(old/p)==h for p,h in original.items())
dest.mkdir(exist_ok=False)
shutil.copytree(old/'source',dest/'source')
for name in ['index_registry.py','routes/rag_query.py','tests/test_independent_edges.py']:
    shutil.copy2(work/'backend'/name,dest/'source/backend'/name)
for name in ['r2-red.log','r2-green.log']:
    shutil.copy2(work/name,dest/name)
py=root/'.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe'
runtime=subprocess.run([str(py),'-B','-c','import sys,sqlite3,numpy,importlib.metadata as m,json; print(json.dumps(dict(python=sys.version,sqlite=sqlite3.sqlite_version,numpy=numpy.__version__,rank_bm25=m.version("rank-bm25"),duckdb=m.version("duckdb"))))'],capture_output=True,text=True,check=True)
source_hashes={str(p.relative_to(dest)).replace('\\','/'):sha(p) for p in (dest/'source').rglob('*') if p.is_file()}
assert all(sha(work/'backend'/p.removeprefix('source/backend/'))==h for p,h in source_hashes.items())
receipt=dict(date=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_hashes=source_hashes,original_manifest_sha256=sha(old/'manifest.json'),original_files=len(original),original_unchanged=True,red_exit=1,red_result='3 failed, 26 passed in 10.58s',green_exit=0,green_result='29 passed, 1 warning in 5.38s',runtime=json.loads(runtime.stdout),command=f'{py} -B -X utf8 -m pytest {work}/backend/tests/test_r8_paged_consumers.py {work}/backend/tests/test_independent_edges.py -q -p no:cacheprovider',limits='Private consumer subset only; timeout config warning because pytest-timeout not installed; no production integration/full coverage/security claim')
(dest/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(__file__,dest/'archive_r2.py')
manifest={str(p.relative_to(dest)).replace('\\','/'):sha(p) for p in dest.rglob('*') if p.is_file()}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(dict(files=len(manifest),manifest_sha256=sha(dest/'manifest.json'),runtime=receipt['runtime'])))
