import pathlib,hashlib,json
p=pathlib.Path('docs/testing/sqlite-vector-r8-20261017');out=pathlib.Path('.tmp/sqlite-r8-r2-review-20261017/adapter')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads((p/'manifest.json').read_text())
for f,v in m.items():
 assert h(p/f)==v['sha256'],f
 if f.startswith(('backend/','tests/')): assert h(out/f)==v['sha256'],f
r={'manifest_sha256':h(p/'manifest.json'),'verified_count':37,'base_plus_four_result':'20 passed, 3 subtests passed in 10.22s','base_plus_four_exit':0,'new_schema_case_result':'1 failed in 0.53s','new_schema_case_exit':1,'test_sha256':h(out/'tests/test_review_core.py'),'log_sha256':h(out.parent/'adapter-review.log'),'schema_log_sha256':h(out.parent/'schema-review.log')}
(out.parent/'adapter-receipt.json').write_text(json.dumps(r,indent=2));print('37hash unchanged; receipt saved')
