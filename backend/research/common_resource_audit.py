"""Post-run wire/resource validation; no Gold, no semantic scoring."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(b):return hashlib.sha256(b).hexdigest()

def audit(profile, *, progress=None):
    reg=load(profile/'registration.json'); status=load(profile/'out/profile-status.json')
    assert digest((profile/'registration.json').read_bytes())==load(profile/'registration.sha256.json')['registration_sha256']
    assert status['status'] in {'FINISHED','STOPPED','GLOBAL_TIME_CAP'}
    assert len(status['units'])==len(reg['schedule'])==54
    resources={a:{'units':0,'statuses':Counter(),'attempts':0,'input_tokens':0,'output_tokens':0,
        'input_bytes':0,'cache_hit_tokens':0,'unknown_cost_requests':0,'max_call_input_tokens':0,
        'max_call_output_tokens':0,'max_unit_input_tokens':0,'max_unit_output_tokens':0,'max_unit_seconds':0} for a in ('P0','A','S')}
    fingerprints=set(); models=set(); units=[]; files={}
    runtime=Path(reg['runtime'])
    texts={sid:(runtime/spec['file']).read_bytes().decode('utf-8') for sid,spec in reg['sources'].items()}
    for unit in reg['schedule']:
        path=profile/'out/units'/unit['unit_id']; result=load(path/'result.json')
        assert all(result[k]==unit[k] for k in ('unit_id','arm','question_id','repeat'))
        files[str((path/'result.json').relative_to(profile))]=digest((path/'result.json').read_bytes())
        ledger=path/'calls/ledger.json'
        state=load(ledger) if ledger.exists() else {'actual_attempts':0,'records':[],'input_bytes':0}
        if ledger.exists():files[str(ledger.relative_to(profile))]=digest(ledger.read_bytes())
        records=[r for r in state['records'] if 'request_wire_utf8' in r]
        assert len(records)==state['actual_attempts']<=unit['planned_max_attempts']<=8
        assert sum(r['input_bytes'] for r in records)==state['input_bytes']<=192000
        input_total=output_total=unknown=0
        for r in records:
            wire=r['request_wire_utf8'].encode(); request=json.loads(r['request_wire_utf8'])
            assert digest(wire)==r['request_sha256'] and len(wire)==r['input_bytes']<=24000
            assert request==r['request'] and request['model']=='deepseek-flash'
            assert request['temperature']==0 and request['thinking']=={'type':'disabled'} and not request.get('stream',False)
            assert request['max_tokens'] in ({300,2048} if unit['arm']=='P0' else {2048})
            usage=r.get('usage')
            if usage:
                assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
                input_total+=usage['prompt_tokens'];output_total+=usage['completion_tokens']
            else:unknown+=1
            if r['status']=='COMPLETED':
                response=json.loads(r['response_wire_utf8'])
                assert digest(r['response_wire_utf8'].encode())==r['response_sha256'] and response==r['response']
                assert response['usage']==usage
                models.add(response.get('model')); fingerprints.add(response.get('system_fingerprint'))
            if result['status']=='COMPLETED':
                assert r['status']=='COMPLETED' and usage and usage['prompt_tokens']<=8192
        if result['status']=='COMPLETED':
            assert input_total<=65536 and output_total<=16384 and result['elapsed_seconds']<=120 and unknown==0
            assert result['answer']
            if unit['arm'] in {'A','S'}:
                chunks=result['chunks'];maps=result['maps']; assert len(records)==len(chunks)+1==len(maps)+1
                for n,(chunk,mapped,r) in enumerate(zip(chunks,maps,records),1):
                    assert mapped['map_call_id']==r['id']==n and mapped['chunk_id']==chunk['chunk_id']
                    body=r['request']['messages'][-1]['content']
                    marker=f"[CHUNK {chunk['chunk_id']}; source {chunk['source_id']}; Unicode [{chunk['start']},{chunk['end']})]\n"
                    assert marker in body and body.split(marker,1)[1] == texts[unit['source_id']][chunk['start']:chunk['end']]
                    assert mapped['output']==r['response']['choices'][0]['message']['content']
                reduce_body=records[-1]['request']['messages'][-1]['content']
                assert json.loads(reduce_body.split('[MAP OUTPUTS]\n',1)[1])==maps
                assert result['answer']==records[-1]['response']['choices'][0]['message']['content']
            else:
                assert result['answer']==result['response']['answer']
                assert result['answer']==result['trace']['native_generator_result']['answer'][:4000]
        resource=resources[unit['arm']];resource['units']+=1;resource['statuses'][result['status']]+=1
        resource['attempts']+=len(records);resource['input_tokens']+=input_total;resource['output_tokens']+=output_total
        resource['input_bytes']+=state['input_bytes'];resource['unknown_cost_requests']+=unknown
        resource['cache_hit_tokens']+=sum(r.get('usage',{}).get('prompt_cache_hit_tokens',0) for r in records)
        resource['max_call_input_tokens']=max([resource['max_call_input_tokens']]+[r.get('usage',{}).get('prompt_tokens',0) for r in records])
        resource['max_call_output_tokens']=max([resource['max_call_output_tokens']]+[r.get('usage',{}).get('completion_tokens',0) for r in records])
        resource['max_unit_input_tokens']=max(resource['max_unit_input_tokens'],input_total)
        resource['max_unit_output_tokens']=max(resource['max_unit_output_tokens'],output_total)
        resource['max_unit_seconds']=max(resource['max_unit_seconds'],result.get('elapsed_seconds',0))
        units.append({**unit,'status':result['status'],'input_tokens':input_total,'output_tokens':output_total,'attempts':len(records),'unknown_cost_requests':unknown})
    assert sum(x['attempts'] for x in resources.values())==status['actual_attempts']<=177
    summary={'status':'WIRE_RESOURCE_AUDIT_PASS','registration_sha256':digest((profile/'registration.json').read_bytes()),
        'profile_status':status['status'],'registered_units':54,'resources':resources,'units':units,
        'response_models':sorted(x for x in models if x),'provider_fingerprints':sorted(x for x in fingerprints if x),
        'file_hashes':files,'total_tokens':sum(x['input_tokens']+x['output_tokens'] for x in resources.values()),
        'parent_elapsed_seconds':status['elapsed_seconds'],'semantic_scoring':'NOT_ASSESSED','scientific_stage':'M2_OPEN'}
    (profile/'resource-audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if progress is not None:
        progress({k:summary[k] for k in ('status','registered_units','total_tokens','parent_elapsed_seconds')})
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,required=True)
    audit(p.parse_args().profile.resolve(), progress=lambda event: print(json.dumps(event)))
