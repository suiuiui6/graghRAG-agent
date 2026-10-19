"""Verify executed public-development receipts; no semantic scoring or Gold."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(b):return hashlib.sha256(b).hexdigest()

def summarize(artifacts,run_root, *, progress=None):
    out,run=Path(artifacts).resolve(),Path(run_root).resolve()
    ledger=read(out/'calls/ledger.json'); registration=read(out/'registration.json')
    inputs=read(out/'inputs.json'); execution=read(out/'execution-status.json')
    assert sha((run/'snapshot.json').read_bytes())==registration['source_snapshot_sha256']
    assert sha((out/'inputs.json').read_bytes())==registration['inputs_sha256']
    snapshot=read(run/'snapshot.json')
    code_unchanged=all(sha((run/p).read_bytes())==h for p,h in snapshot['files'].items())
    sources_unchanged=all(sha(Path(p).read_bytes())==h for p,h in inputs['input_hashes'].items())
    sent=[r for r in ledger['records'] if r.get('id')]
    assert len(sent)==ledger['actual_attempts']<=72
    assert sum(r['input_bytes'] for r in sent)==ledger['input_bytes']<=1200000
    phases=defaultdict(list)
    for r in sent:
        raw=r['request_wire_utf8'].encode('utf-8')
        assert sha(raw)==r['request_sha256'] and len(raw)==r['input_bytes']
        assert json.loads(raw)==r['request']
        assert r['request']['model']=='deepseek-flash' and r['request']['thinking']=={'type':'disabled'}
        if r['status']=='COMPLETED':
            raw=r['response_wire_utf8'].encode('utf-8')
            assert sha(raw)==r['response_sha256'] and json.loads(raw)==r['response']
            assert r['response']['usage']==r['usage']
        if r.get('usage'):
            u=r['usage'];assert u['total_tokens']==u['prompt_tokens']+u['completion_tokens']
        phases[r['phase']].append(r)
    def stats(rows):
        valid=[r for r in rows if r.get('usage')]
        return {'attempts':len(rows),'completed':sum(r['status']=='COMPLETED' for r in rows),
            'known_usage':{k:sum(r['usage'][k] for r in valid) for k in ('prompt_tokens','completion_tokens','total_tokens')},
            'unknown_cost_attempts':sum(r.get('cost_status')!='KNOWN' for r in rows),
            'input_request_json_bytes':sum(r['input_bytes'] for r in rows),
            'sum_call_seconds':sum(r.get('elapsed_seconds',0) for r in rows),
            'max_single_input_tokens':max((r['usage']['prompt_tokens'] for r in valid),default=None),
            'max_single_output_tokens':max((r['usage']['completion_tokens'] for r in valid),default=None),
            'cache_hit_input_tokens':sum(r['usage'].get('prompt_cache_hit_tokens',r['usage'].get('prompt_tokens_details',{}).get('cached_tokens',0)) for r in valid)}
    byquestion={phase:{qid:stats([r for r in rows if r['question_id']==qid])
                      for qid in sorted({r['question_id'] for r in rows})} for phase,rows in phases.items() if phase!='index'}
    a_checks=[]
    for w in inputs['work']:
        path=out/f"{w['question_id']}.a.json"
        if not path.exists():continue
        data=read(path);rows=[r for r in phases['a'] if r['question_id']==w['question_id']]
        assert len(rows)==len(w['chunks'])+1 and len(data['maps'])==len(w['chunks'])
        source_record=next(s for s in read(Path(inputs['data_dir'])/'sources.json') if s['source_id']==w['source_id'])
        text=(Path(inputs['data_dir'])/source_record['canonical_file']).read_bytes().decode('utf-8')
        for c,m,r in zip(w['chunks'],data['maps'],rows):
            assert r['request']['messages'][-1]['content'].endswith(text[c['start']:c['end']])
            assert m['output']==r['response']['choices'][0]['message']['content']
        reduce=rows[-1]['request']['messages'][-1]['content']
        assert json.loads(reduce.split('[MAP OUTPUTS]\n',1)[1])==data['maps']
        assert data['answer']==rows[-1]['response']['choices'][0]['message']['content']
        a_checks.append({'question_id':w['question_id'],'selected_input_slices_match':True,
                         'map_to_reduce_complete':True,'semantic_scope_correctness':'NOT_ASSESSED'})
    p0=[]
    for w in inputs['work']:
        path=run/'artifacts'/f"{w['question_id']}.p0.json"
        if not path.exists():continue
        data=read(path);native=data['trace'].get('native_generator_result')
        api=data['response']['answer']
        if native is not None:assert api==native['answer'][:4000]
        p0.append({'question_id':w['question_id'],'document_id':data['document_id'],
                   'api_answer_characters':len(api),'native_generation_entered':native is not None,
                   'status':data['response'].get('metadata',{}).get('status'),
                   'api_4000_limit_verified':native is not None,
                   'semantic_scoring':'NOT_EXECUTED'})
    result={'status':'EXECUTED_RECEIPTS_VERIFIED','execution_date':'2026-10-15',
        'all_steps_completed':execution.get('all_steps_completed',False),'guard_closed':ledger['closed'],
        'stop_reason':ledger.get('stop_reason'),'by_phase':{p:stats(rows) for p,rows in phases.items()},
        'by_question':byquestion,'total':stats(sent),'local_total_seconds':execution['elapsed_seconds'],
        'provider_models':sorted({r.get('response',{}).get('model') for r in sent if r.get('response',{}).get('model')}),
        'provider_fingerprints':sorted({r.get('response',{}).get('system_fingerprint') for r in sent if r.get('response',{}).get('system_fingerprint')}),
        'wire_temperature_by_phase':{p:{'omitted_calls':sum('temperature' not in r['request'] for r in rows),
            'explicit_values':sorted({r['request']['temperature'] for r in rows if 'temperature' in r['request']})}
            for p,rows in phases.items()},
        'index_result':read(run/'artifacts/index-result.json') if (run/'artifacts/index-result.json').exists() else None,
        'A_input_chain_checks':a_checks,'P0_native_route_checks':p0,
        'snapshot_files_verified':len(snapshot['files']),'code_unchanged':code_unchanged,'source_inputs_unchanged':sources_unchanged,
        'same_weight_snapshot_verified':False,'three_arm_controlled_comparison':False,
        'semantic_scoring':'NOT_EXECUTED','human_gold_verified':False,'heldout_H1':[],'heldout_H2':[],
        'scientific_stage':'M2_OPEN'}
    (out/'resource-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if progress is not None:
        progress({k:result[k] for k in ('status','all_steps_completed','guard_closed','by_phase','total','provider_models','local_total_seconds')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts',required=True);p.add_argument('--run-root',required=True)
    a=p.parse_args();summarize(a.artifacts,a.run_root, progress=lambda event: print(json.dumps(event,ensure_ascii=False)))
