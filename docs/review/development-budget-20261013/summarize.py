"""Verify receipts and summarize descriptive resource measurements only."""
import hashlib
import json
import platform
import statistics
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / 'run-01'
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
digest = lambda b: hashlib.sha256(b).hexdigest()
manifest, ledger, summary = load(HERE/'manifest.json'), load(RUN/'ledger.json'), load(RUN/'summary.json')
assert len(ledger) <= manifest['max_calls']
groups = defaultdict(list)
for call in ledger:
    if 'request_path' not in call:
        continue
    reqpath, respath = RUN/call['request_path'], RUN/call['response_path']
    assert digest(reqpath.read_bytes()) == call['request_sha256']
    assert digest(respath.read_bytes()) == call['response_sha256']
    req, res = load(reqpath), load(respath)
    serialized = json.dumps(req['messages'],ensure_ascii=False,separators=(',',':')).encode('utf-8')
    assert digest(serialized) == call['messages_sha256'] and len(serialized) == call['messages_utf8_bytes']
    assert req['max_tokens'] == 2048 and req['model'] == manifest['model_requested'] and req['temperature'] == 0
    assert call['status'] == res['status']
    if call.get('usage_known'):
        u = call['usage']
        assert u['total_tokens'] == u['prompt_tokens'] + u['completion_tokens']
    groups[call['arm']].append(call)

def stats(calls):
    valid = [c for c in calls if c.get('usage_known')]
    return {'calls':len(calls), 'successful_calls':sum(c['status']=='SUCCESS' for c in calls),
            'known_usage_subtotal':{k:sum(c['usage'][k] for c in valid) for k in ('prompt_tokens','completion_tokens','total_tokens')},
            'max_single_input_tokens':max((c['usage']['prompt_tokens'] for c in valid),default=None),
            'max_single_output_tokens':max((c['usage']['completion_tokens'] for c in valid),default=None),
            'sum_local_call_seconds':sum(c['elapsed_seconds'] for c in calls),
            'median_local_call_seconds':statistics.median(c['elapsed_seconds'] for c in calls) if calls else None,
            'cache_hit_input_tokens':sum(c['usage'].get('prompt_cache_hit_tokens',0) for c in valid),
            'unknown_cost_calls':sum(not c['usage_known'] and c['send_status']!='NOT_ATTEMPTED' for c in calls)}

s = groups['S_SCAN_ALL']
byquestion = {qid:stats([c for c in s if c['question_id']==qid]) for qid in sorted({c['question_id'] for c in s})}
coverage = {}
for qid in byquestion:
    intervals = [i for c in s if c['question_id']==qid and c.get('stage')=='map' and c['status']=='SUCCESS' for i in c['coverage']]
    source = intervals[0]['source_id'] if intervals else None
    spans = sorted((i['start'],i['end']) for i in intervals)
    cursor = 0
    contiguous = True
    for start,end in spans:
        contiguous = contiguous and start==cursor
        cursor=end
    coverage[qid] = {'successful_map_intervals':spans, 'source_id':source,
                     'full_text_input_traversal': bool(source and contiguous and cursor==manifest['source_counts'][source]['unicode_characters']),
                     'semantic_completeness':'NOT_ASSESSED'}
assert sum(c.get('messages_utf8_bytes',0) for c in ledger) == summary['messages_utf8_bytes'] <= manifest['messages_utf8_budget']
known = stats([c for c in ledger if 'request_path' in c])['known_usage_subtotal']
assert known == summary['known_usage_subtotal']
result = {'verified_utc':datetime.now(timezone.utc).isoformat(), 'status':'RECEIPTS_VERIFIED',
          'profile_status':summary['status'], 'python_version':platform.python_version(),
          'provider_models':sorted({c['provider_model'] for c in ledger if c.get('provider_model')}),
          'provider_fingerprints_present':sum(bool(c.get('system_fingerprint')) for c in ledger),
          'P0_NATIVE':manifest['P0_NATIVE'],
          'A_AUTO_READ':{'resolved':sum(r['status']=='RESOLVED' for r in manifest['auto_resolution']),
                         'unresolved':sum(r['status']=='UNRESOLVED' for r in manifest['auto_resolution']),
                         'model_calls':0,'answer_budget_measured':False},
          'by_arm':{k:stats(v) for k,v in groups.items()}, 'S_by_question':byquestion,
          'input_traversal':coverage, 'all_known_usage':known,
          'global_local_elapsed_seconds':summary['elapsed_seconds'],
          'code_unchanged':summary['code_unchanged'],
          'source_inputs_unchanged':all(digest((ROOT/'docs/review/public-development-20261012/pilot/validated'/p).read_bytes())==h for p,h in manifest['inputs_sha256'].items()),
          'same_weight_snapshot_verified':False, 'three_baseline_budget_frozen':False,
          'statistical_inference':'NONE; 6 correlated development questions in 2 source units, one profile each',
          'semantic_scoring':'NOT_EXECUTED', 'scientific_stage':'M2_OPEN'}
(HERE/'resource-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
