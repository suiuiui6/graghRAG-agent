import hashlib
import json
from pathlib import Path
import httpx
import pytest
from research.common_three_arm import build_schedule, scan_chunks, unit_guard_class, ResourceCap, verify_files, prove_p0_path, supervise, clear_unit_cache, child_environment


def response(prompt=20, completion=10):
    return {'model':'deepseek-flash','system_fingerprint':'f','choices':[{'finish_reason':'stop','message':{'content':'answer'}}], 'usage':{'prompt_tokens':prompt,'completion_tokens':completion,'total_tokens':prompt+completion}}


def payload():
    return {'model':'deepseek-flash','temperature':0.0,'max_tokens':2048,'thinking':{'type':'disabled'},'messages':[{'role':'user','content':'中文'}]}


def test_balanced_schedule_has_54_unique_units():
    schedule=build_schedule([{'question_id':f'Q{i}','source_id':'S','question':'问题'} for i in range(6)])
    assert len(schedule)==54 and len({x['unit_id'] for x in schedule})==54
    for q in range(6):
        units=[x for x in schedule if x['question_id']==f'Q{q}']
        assert len(units)==9
        for position in range(3):
            assert {units[r*3+position]['arm'] for r in range(3)}=={'P0','A','S'}


def test_scan_exact_unicode_intervals_cover_whole_source_once():
    text='α中文😀'*5000
    chunks=scan_chunks('S',text)
    assert ''.join(text[c['start']:c['end']] for c in chunks)==text
    assert all(c['end']-c['start']<=8000 for c in chunks)
    assert chunks[0]['start']==0 and chunks[-1]['end']==len(text)


def test_common_guard_actual_post_tokens_cap_is_known_resource(tmp_path):
    Guard=unit_guard_class(); guard=Guard(tmp_path,'fake-secret','A',planned_calls=2)
    with guard.install(),guard.phase('a'),pytest.raises(ResourceCap):
        httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response(8193)))).post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.state['stop_kind']=='RESOURCE_CAP'
    assert guard.actual_attempts==1 and guard.state['records'][0]['cost_status']=='KNOWN'


def test_common_guard_presend_bytes_does_not_spend(tmp_path):
    Guard=unit_guard_class(); guard=Guard(tmp_path,'fake-secret','S',planned_calls=7)
    p=payload();p['messages'][0]['content']='a'*24000
    with guard.install(),guard.phase('a'),pytest.raises(ResourceCap):
        httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('sent'))).post('https://api.deepseek.com/chat/completions',json=p)
    assert guard.actual_attempts==0


def test_common_guard_temperature_drift_stops_profile(tmp_path):
    Guard=unit_guard_class();guard=Guard(tmp_path,'fake-secret','P0',planned_calls=3)
    p=payload();p['temperature']=0.5
    with guard.install(),guard.phase('p0'),pytest.raises(Exception):
        httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('sent'))).post('https://api.deepseek.com/chat/completions',json=p)
    assert guard.closed and guard.state['stop_kind']=='PROFILE_STOP'
    assert guard.actual_attempts==0


def test_common_guard_unknown_usage_stops_profile(tmp_path):
    Guard=unit_guard_class();guard=Guard(tmp_path,'fake-secret','A',planned_calls=2)
    data=response();data.pop('usage')
    with guard.install(),guard.phase('a'),pytest.raises(Exception):
        httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))).post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.state['stop_kind']=='PROFILE_STOP'


def test_hash_drift_is_rejected(tmp_path):
    path=tmp_path/'x';path.write_text('old'); hashes={'x':hashlib.sha256(path.read_bytes()).hexdigest()}
    verify_files(tmp_path,hashes);path.write_text('new')
    with pytest.raises(ValueError):verify_files(tmp_path,hashes)


def test_frozen_p0_call_bound_uses_one_preprocess_plus_two_generation():
    root=Path(__file__).resolve().parents[2]/'.tmp/public-dev-budget-20261015-r2'
    proof=prove_p0_path(root)
    assert proof['preprocess_attempts']==1
    assert proof['generation_attempts']==2
    assert proof['per_unit_max_attempts']==3
    assert proof['enable_global_mode'] is False


def test_guard_attempt_cap_refuses_ninth_send(tmp_path):
    guard=unit_guard_class()(tmp_path,'fake-secret','S',planned_calls=9)
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response())))
    with guard.install(),guard.phase('a'):
        for _ in range(8):client.post('https://api.deepseek.com/chat/completions',json=payload())
        with pytest.raises(ResourceCap):client.post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.actual_attempts==8


def test_guard_cumulative_output_cap_is_known_cost(tmp_path):
    guard=unit_guard_class()(tmp_path,'fake-secret','S',planned_calls=8)
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response(completion=9000))))
    with guard.install(),guard.phase('a'):
        client.post('https://api.deepseek.com/chat/completions',json=payload())
        with pytest.raises(ResourceCap):client.post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.actual_attempts==2
    assert sum(r.get('usage',{}).get('completion_tokens',0) for r in guard.state['records'])==18000


def test_guard_shared_input_bytes_limit_blocks_next_request(tmp_path):
    guard=unit_guard_class()(tmp_path,'fake-secret','S',planned_calls=8)
    # Reserve prior accumulated inputs, then exercise real transport interception.
    guard.state['input_bytes']=191990;guard._save()
    with guard.install(),guard.phase('a'),pytest.raises(ResourceCap):
        httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('sent'))).post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.actual_attempts==0 and guard.state['input_bytes']==191990


def test_actual_sdk_httpx2_and_p0_preprocess_limit_are_accounted(tmp_path):
    from research.development_budget import openai_transport_module
    sdk_http=openai_transport_module();guard=unit_guard_class()(tmp_path,'fake-secret','P0',planned_calls=3)
    p=payload();p['max_tokens']=300
    with guard.install(),guard.phase('p0'):
        sdk_http.Client(transport=sdk_http.MockTransport(lambda r:sdk_http.Response(200,json=response()))).post('https://api.deepseek.com/chat/completions',json=p)
    assert guard.actual_attempts==1 and guard.state['records'][0]['transport']==sdk_http.__name__


def test_unit_expired_during_startup_refuses_first_send(tmp_path):
    guard=unit_guard_class()(tmp_path,'fake-secret','P0',planned_calls=3,deadline=1)
    with guard.install(),guard.phase('p0'),pytest.raises(Exception):
        httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('sent'))).post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.actual_attempts==0 and guard.state['stop_kind']=='PROFILE_STOP'


def _supervisor_fixture(tmp_path,monkeypatch,statuses):
    import research.common_three_arm as runner
    import dotenv
    import subprocess
    schedule=build_schedule([{'question_id':f'Q{i}','source_id':'S'} for i in range(6)])
    for unit in schedule:unit['planned_max_attempts']=3
    reg={'runtime':str(tmp_path/'runtime'),'schedule':schedule}
    monkeypatch.setattr(runner,'verify_registration',lambda p:reg)
    monkeypatch.setattr(dotenv,'dotenv_values',lambda p:{'LANGEXTRACT_API_KEY':'fake-secret'})
    called=[]
    def child(command,**kwargs):
        unit=next(u for u in schedule if u['unit_id']==command[command.index('--unit-id')+1]);called.append(unit)
        status=statuses[min(len(called)-1,len(statuses)-1)]
        if status=='TIMEOUT':raise subprocess.TimeoutExpired(command,kwargs['timeout'])
        runner.dump(tmp_path/'out/units'/unit['unit_id']/'result.json',{**unit,'status':status,'answer':'a' if status=='COMPLETED' else None,'actual_attempts':1})
        return subprocess.CompletedProcess(command,0,stdout='safe',stderr='')
    monkeypatch.setattr(subprocess,'run',child)
    return called,schedule


def test_resource_cap_continues_but_unknown_stops_all_remaining_units(tmp_path,monkeypatch):
    called,schedule=_supervisor_fixture(tmp_path,monkeypatch,['RESOURCE_CAP','PROFILE_STOP'])
    result=supervise(tmp_path,'not-read.env')
    assert len(called)==2 and len(result['units'])==54
    assert result['units'][0]['status']=='RESOURCE_CAP'
    assert all(u['status']=='NOT_RUN' for u in result['units'][2:])
    assert all((tmp_path/'out/units'/u['unit_id']/'result.json').exists() for u in schedule)


def test_child_timeout_stops_profile_and_preserves_54_denominator(tmp_path,monkeypatch):
    called,schedule=_supervisor_fixture(tmp_path,monkeypatch,['TIMEOUT'])
    result=supervise(tmp_path,'not-read.env')
    assert len(called)==1 and len(result['units'])==54
    assert result['units'][0]['status']=='PROFILE_STOP'
    assert all(u['status']=='NOT_RUN' for u in result['units'][1:])
    assert all((tmp_path/'out/units'/u['unit_id']/'result.json').exists() for u in schedule)


def test_global_remaining_attempts_are_checked_before_send(tmp_path):
    guard=unit_guard_class()(tmp_path,'fake-secret','P0',planned_calls=3,global_attempts_remaining=1)
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response())))
    with guard.install(),guard.phase('p0'):
        client.post('https://api.deepseek.com/chat/completions',json=payload())
        with pytest.raises(Exception):client.post('https://api.deepseek.com/chat/completions',json=payload())
    assert guard.actual_attempts==1 and guard.state['stop_kind']=='PROFILE_STOP'


@pytest.mark.parametrize('tokens',[300,2049,4096])
def test_map_reduce_output_limit_cannot_be_overridden(tmp_path,tokens):
    guard=unit_guard_class()(tmp_path,'fake-secret','A',planned_calls=2)
    p=payload();p['max_tokens']=tokens
    with guard.install(),guard.phase('a'),pytest.raises(Exception):
        httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('sent'))).post('https://api.deepseek.com/chat/completions',json=p)
    assert guard.actual_attempts==0 and guard.state['stop_kind']=='PROFILE_STOP'


def test_global_time_budget_keeps_all_units_without_starting_child(tmp_path,monkeypatch):
    import research.common_three_arm as runner
    called,schedule=_supervisor_fixture(tmp_path,monkeypatch,['COMPLETED'])
    times=iter([0,5401]+[5401]*100)
    monkeypatch.setattr(runner.time,'time',lambda:next(times))
    result=supervise(tmp_path,'not-read.env')
    assert called==[] and len(result['units'])==54
    assert result['status']=='GLOBAL_TIME_CAP'
    assert all(u['status']=='NOT_RUN' for u in result['units'])


def test_cache_cleanup_removes_only_new_runtime_rewrite_files(tmp_path):
    runtime=tmp_path/'runtime';output=runtime/'backend/output';output.mkdir(parents=True)
    for suffix in ('','-wal','-shm','-journal'):(output/('rewrite-cache.sqlite3'+suffix)).write_text('cache')
    kept=output/'nodes.json';kept.write_text('unchanged')
    clear_unit_cache(tmp_path,{'runtime':str(runtime)})
    assert kept.read_text()=='unchanged'
    assert not list(output.glob('rewrite-cache.sqlite3*'))


def test_cache_cleanup_refuses_frozen_or_external_root(tmp_path):
    with pytest.raises(ValueError):clear_unit_cache(tmp_path,{'runtime':str(tmp_path.parent)})


def test_child_environment_inherits_only_allowlisted_settings(tmp_path,monkeypatch):
    monkeypatch.setenv('UNRELATED_API_KEY','must-not-inherit')
    monkeypatch.setenv('HOME','outside-home')
    env=child_environment(tmp_path,'fake-secret')
    assert 'UNRELATED_API_KEY' not in env
    assert env['HOME']==str(tmp_path/'home')
    assert env['LANGEXTRACT_TEMPERATURE']=='0.0'
    assert env['LANGEXTRACT_API_KEY']=='fake-secret'
    assert env['HF_HUB_OFFLINE']=='1' and env['PYTHONNOUSERSITE']=='1'


def test_A_recomputes_resolution_and_rejects_registered_range_drift():
    from dataclasses import asdict
    from research.development_structure import StructureIndex, StructureNode
    from research.development_scope import resolve_development_scope
    from research.scope_v2 import Source
    from research.common_three_arm import resolve_a_work
    text='4. Phase\nα资料一\n5. Next\n资料二'
    index=StructureIndex('S',hashlib.sha256(text.encode()).hexdigest(),(
        StructureNode('heading',0,8,1,'4','4. Phase'),StructureNode('heading',text.index('5.'),text.index('5.')+7,1,'5','5. Next')),{})
    query='列出第4节的全部资料';resolution=resolve_development_scope(query,[Source('S',text)],[index])
    end=text.index('5.')
    work={'source_id':'S','question':query,'resolution':json.loads(json.dumps(asdict(resolution))),
          'chunks':[{'source_id':'S','start':0,'end':end,'chunk_id':f'S-A-0-{end}'}]}
    registration={'heading_structures':{'S':{'structure':asdict(index)}}}
    actual=resolve_a_work(work,registration,text)
    assert actual['chunks']==work['chunks'] and actual['local_resolution_seconds']>=0
    work['chunks'][0]['end']-=1
    with pytest.raises(ValueError):resolve_a_work(work,registration,text)


def test_map_reduce_records_body_and_heading_inputs_separately(tmp_path,monkeypatch):
    import requests
    from research.common_three_arm import map_reduce
    def offline(session,request,**kwargs):
        result=requests.Response();result.status_code=200
        result._content=json.dumps(response()).encode();return result
    monkeypatch.setattr(requests.Session,'send',offline)
    text='4. Phase\nexact canonical body'
    chunks=scan_chunks('S',text)
    reg={'sources':{'S':{'chunks':chunks}},'heading_structures':{'S':{'structure':{'nodes':[{'kind':'heading','title':'4. Phase','start':0,'end':8}]}}},
         'system_prompt':'sys','map_instruction':'map','reduce_instruction':'reduce'}
    guard=unit_guard_class()(tmp_path,'fake-secret','S',planned_calls=2)
    with guard.install():result=map_reduce({'arm':'S','source_id':'S','question_id':'Q'}, {'question':'问题'},reg,guard,text)
    assert guard.actual_attempts==2
    assert text in guard.state['records'][0]['request']['messages'][1]['content']
    assert result['body_source_intervals']==[{'source_id':'S','start':0,'end':len(text)}]
    assert result['structure_metadata_input']==[{'heading':'4. Phase','start':0,'end':8}]
    assert result['actual_model_input_intervals_scope']=='body_only; structure metadata recorded separately'
