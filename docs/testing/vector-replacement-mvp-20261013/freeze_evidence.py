import datetime
import hashlib
import json
import pathlib
import shutil

root=pathlib.Path(__file__).resolve().parent
dest=root.parents[1]/'docs/testing/vector-replacement-mvp-20261013'
dest.mkdir(parents=True,exist_ok=True)
chroma=json.loads(sorted(root.glob('filters-chroma-*.json'))[-1].read_text(encoding='utf-8'))
lance=json.loads(sorted(root.glob('filters-lance-*.json'))[-1].read_text(encoding='utf-8'))
diff=[]
for a,b in zip(chroma['cases'],lance['cases'],strict=True):
    assert a['where']==b['where']
    if (a['status'],a.get('ids'))!=(b['status'],b.get('ids')):
        diff.append({'where':a['where'],'chroma':a,'lance':b})
assert len(chroma['cases'])==18 and len(diff)==5
summary={'status':'NATIVE_CAPABILITY_PASS_COMPATIBILITY_BLOCKED','cases':18,'different':len(diff),'same':18-len(diff),'differences':diff,'not_run':['complete_VectorStore_adapter','all_consumer_paths','pagination_fixed_generation_5001','100k_scale','30_warmup_100_measurements','RSS_measurements','topk_full_numpy_differential','Chroma_duplicate_id_differential','process_kill_power_loss_recovery','parallel_process_writers','application_wide_migration_barrier','real_data_read_only_inventory','production_dependency_merge_audit','backend_full_acceptance_and_dual90']}
(root/'filter-differential-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
names=['pyproject.toml','uv.lock','uv-with-audit-original.lock','runtime-registry.txt','installed-identity.json','probe.py','sqlite_reference.py','filter_differential.py','freeze_evidence.py','filter-differential-summary.json']
for pattern in ['*.log','*.exit','results-*.json','sqlite-results-*.json','filters-*.json','runtime-audit-*.json']:
    names.extend(p.name for p in root.glob(pattern))
receipts=[]
for name in sorted(set(names)):
    source=root/name
    shutil.copy2(source,dest/name)
    receipts.append({'file':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size})
manifest={'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_root':str(root),'files':receipts,'synthetic_data_policy':'Only generated values; database files remain in exclusive tmp and are not product artifacts. Reproduction scripts preserved.','summary':summary}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files':len(receipts),'manifest_sha256':hashlib.sha256((dest/'manifest.json').read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256((root/'probe.py').read_bytes()).hexdigest(),'lock_sha256':hashlib.sha256((root/'uv.lock').read_bytes()).hexdigest(),'filter_differences':len(diff)}))
