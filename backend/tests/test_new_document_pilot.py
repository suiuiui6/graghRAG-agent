import json
from pathlib import Path
import subprocess
import sys
import pytest
import httpx
from research import new_document_pilot as pilot


@pytest.mark.parametrize('mode',['unknown','oversize','known_over_token','two_attempts'])
def test_index_guard_real_transport_cost_and_budget(tmp_path,mode):
    from research.development_budget import BudgetLimits,BudgetStopped
    cap={'seconds':1800,'single_input_bytes':24000,'actual_prompt_tokens':16384,'actual_completion_tokens':8192}
    guard=pilot.index_guard_class(cap)(tmp_path,'local-test-secret',BudgetLimits(total_attempts=2,index_attempts=2,p0_attempts=0,a_attempts=0,input_bytes=48000,window_seconds=1800))
    request={'model':'deepseek-flash','max_tokens':4096,'thinking':{'type':'disabled'},'messages':[{'role':'user','content':'x'*25000 if mode=='oversize' else 'test'}]}
    tokens=8193 if mode=='known_over_token' else 10
    reply={'choices':[{'finish_reason':'stop','message':{'content':'{"extractions": []}'}}]}
    if mode!='unknown':reply['usage']={'prompt_tokens':tokens,'completion_tokens':1,'total_tokens':tokens+1}
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=reply))) as client,guard.install(),guard.phase('index','S'):
        if mode=='two_attempts':
            for _ in range(2):client.post('https://api.deepseek.com/chat/completions',json=request)
            with pytest.raises(BudgetStopped):client.post('https://api.deepseek.com/chat/completions',json=request)
            assert guard.actual_attempts==2
        else:
            with pytest.raises(BudgetStopped):client.post('https://api.deepseek.com/chat/completions',json=request)
            assert guard.closed
            assert guard.actual_attempts==(0 if mode=='oversize' else 1)
            if mode=='unknown':assert guard.state['records'][0]['cost_status']=='UNKNOWN'
            if mode=='known_over_token':assert guard.state['records'][0]['cost_status']=='KNOWN'


def test_dynamic_bound_balanced_unresolved_and_full_tail():
    work=[{'question_id':'Q1','source_id':'S','resolution':{'status':'UNRESOLVED'},'chunks':[]},
          {'question_id':'Q2','source_id':'S','resolution':{'status':'RESOLVED'},'chunks':[{},{}]}]
    sources={'S':{'chunks':pilot.common.scan_chunks('S','x'*16001)}}
    rows=pilot.dynamic_schedule(work,sources)
    assert len(rows)==18
    assert sum(r['planned_max_attempts'] for r in rows)==3*(3+0+4+3+3+4)
    assert all(r['planned_max_attempts']==0 for r in rows if r['question_id']=='Q1' and r['arm']=='A')
    for q in ('Q1','Q2'):
        qrows=[r for r in rows if r['question_id']==q]
        for position in range(3):assert {qrows[r*3+position]['arm'] for r in range(3)}=={'P0','A','S'}
    assert sources['S']['chunks'][-1]['end']==16001


@pytest.mark.parametrize('qid',['../outside','Q/one','', '题'])
def test_questions_reject_path_escape_and_invalid_ids(qid):
    with pytest.raises(ValueError):pilot.validate_questions([{'question_id':qid,'source_id':'S','question':'第1节清单','range_condition':'explicit'}],'S')


def test_questions_source_identity_and_extra_oracle_fields_rejected():
    q={'question_id':'Q','source_id':'S','question':'第1节清单','range_condition':'explicit'}
    pilot.validate_questions([q],'S')
    with pytest.raises(ValueError):pilot.validate_questions([q],'OTHER')
    with pytest.raises(ValueError):pilot.validate_questions([{**q,'gold_heading':'1'}],'S')
    with pytest.raises(ValueError):pilot.validate_questions([q,q],'S')


def test_unresolved_preserved_without_request_or_index(monkeypatch,tmp_path):
    unit={'unit_id':'Q-r1-A','arm':'A','planned_max_attempts':0}
    monkeypatch.setattr(pilot,'verify_registration',lambda p:{'schedule':[unit]})
    monkeypatch.setattr(pilot.common,'run_worker',lambda *a:pytest.fail('不得请求'))
    row=pilot.worker(tmp_path,unit['unit_id'],0,0)
    assert row['status']=='UNRESOLVED' and row['actual_attempts']==0
    assert json.loads((tmp_path/'out/units/Q-r1-A/result.json').read_text(encoding='utf8'))==row


def test_native_sdk_mock_preflight_and_registration_real_frozen_snapshot(tmp_path):
    repo=Path(__file__).resolve().parents[2]
    frozen=repo/'.tmp/public-dev-budget-20261015-r2'
    prompt=repo/'.tmp/simple-output-20261016'
    if not frozen.exists() or not prompt.exists():pytest.skip('需要已登记本地研究快照')
    data=tmp_path/'data';data.mkdir()
    # Synthetic parser fixture: PDF bytes are an identity placeholder only;
    # the actual native bridge consumes canonical page map and Poppler XML.
    raw=data/'synthetic.pdf';raw.write_bytes(b'%PDF-1.4\n% synthetic identity fixture\n')
    text='7. Setup\nOnly synthetic parameter A equals 2 units.\n'
    canonical=data/'synthetic.txt';canonical.write_text(text,encoding='utf8',newline='')
    page=data/'pages.json';pilot.dump(page,{'pages':[{'start':0,'end':len(text),'pdf_page_zero_based':0,'pdf_page_one_based':1,'text':text}]})
    xml=data/'synthetic.xml';xml.write_text('<pdf2xml><page number="1"><fontspec id="1" family="Times,Bold"/><fontspec id="2" family="Times"/><text font="1">7. Setup</text><text font="2">Only synthetic parameter A equals 2 units.</text></page></pdf2xml>',encoding='utf8')
    manifest=data/'sources.json';pilot.dump(manifest,[{'source_id':'SYNTHETIC','raw_file':raw.name,'canonical_file':canonical.name,'section_or_page_map':page.name,'source_sha256':pilot.sha(raw),'canonical_sha256':pilot.sha(canonical)}])
    questions=data/'questions.input.json';pilot.dump(questions,[{'question_id':'SYN-Q','source_id':'SYNTHETIC','question':'List the parameters in section 7.','range_condition':'explicit'}])
    batch=data/'batch.json';pilot.dump(batch,{'sources':[{'source_id':'SYNTHETIC','manifest_file':manifest.name,'xml_file':xml.name,'questions_file':questions.name}]})
    root=tmp_path/'profile'
    result=pilot.prepare(batch,frozen,prompt,root)
    assert result['total_units']==9
    reg=pilot.verify_registration(root/'SYNTHETIC')
    pf=pilot.load(Path(reg['runtime'])/'artifacts/preflight.json')
    assert pf['planned_requests']>0 and pf['sdk_transport_module'] in ('httpx','httpx2')
    assert all(r['request']['model']=='deepseek-flash' for r in pf['requests'])
    assert reg['index_budget']['attempts']==pf['planned_requests']*2+4
    assert reg['index_budget']['input_bytes']==pf['planned_input_bytes']*2+24000
    assert reg['system_prompt']==pilot.load(prompt/'registration.json')['system_prompt']
    assert len(reg['source_code_files'])==147
    assert not (Path(reg['runtime'])/'backend/.env').exists()
    assert reg['common_budget']['global_path_attempts']==reg['global_path_attempts']
    assert reg['common_budget']['global_seconds']==reg['global_seconds']
    copy=Path(reg['runtime'])/reg['sources']['SYNTHETIC']['file']
    copy.write_bytes(b'drift')
    with pytest.raises(ValueError,match='漂移'):pilot.verify_registration(root/'SYNTHETIC')
    copy.write_bytes(canonical.read_bytes())
    canonical.write_text(text+'drift',encoding='utf8')
    with pytest.raises(ValueError,match='漂移'):pilot.verify_registration(root/'SYNTHETIC')
