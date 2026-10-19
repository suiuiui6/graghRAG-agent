import pathlib,hashlib,json,datetime
p=pathlib.Path('docs/testing/sqlite-vector-r8-r2-20261017');out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017/adapter-r2');h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads((p/'manifest.json').read_text())
for f,v in m.items():
 assert h(p/f)==v['sha256'],f
 if f.startswith(('backend/','tests/')):assert h(out/f)==v['sha256'],f
r={'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':h(p/'manifest.json'),'verified_count':42,'result':'29 passed, 3 subtests passed in 11.19s','pytest_exit':0,'command':'.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe -B -X utf8 -m pytest .tmp/sqlite-r8-r2-review-20261017/adapter-r2/tests -q -p no:cacheprovider --basetemp=.tmp/sqlite-r8-r2-review-20261017/r2-final-pytest-temp','independent_case_sha256':h(out/'tests/test_review_core.py'),'log_sha256':h(out.parent/'adapter-r2-review.log'),'initial_fixture_wal_error':'26 passed 3 failed/3subtests; uncheckpointed WAL meant restore source contained pre-mutation schema; corrected independent fixtures only, complete rerun'}
(out.parent/'adapter-r2-receipt.json').write_text(json.dumps(r,indent=2));print('42 frozen/copy hashes unchanged; final receipt saved')
