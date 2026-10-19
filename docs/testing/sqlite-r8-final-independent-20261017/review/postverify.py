import pathlib, hashlib, json, datetime
root=pathlib.Path('docs/testing/sqlite-r8-consumers-r2-20261017'); out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((root/'manifest.json').read_text())
for f,v in m.items():
 assert h(root/f)==v,f
 if f.startswith('source/'): assert h(out/f)==v,f
r={'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frozen_manifest_sha256':h(root/'manifest.json'),'verified_count':len(m),'pytest_exit':0,'result':'32 passed in 4.79s','command':'.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe -B -X utf8 -m pytest .tmp/sqlite-r8-r2-review-20261017/source/backend/tests/test_r8_paged_consumers.py .tmp/sqlite-r8-r2-review-20261017/source/backend/tests/test_independent_edges.py .tmp/sqlite-r8-r2-review-20261017/source/backend/tests/test_r2_review_edges.py -q -p no:cacheprovider','independent_tests_sha256':h(out/'source/backend/tests/test_r2_review_edges.py'),'log_sha256':h(out/'review.log'),'prior_fixture_error':'Chunk content_type omitted in reviewer test; corrected test only; prior run 31 pass / 1 fail exit1, fixture-error.log retained'}
(out/'receipt.json').write_text(json.dumps(r,indent=2))
print('post-run frozen/source hashes all unchanged')
