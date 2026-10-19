"""Bounded, source-isolated exploratory PDF pilot. Prepare never opens Gold/env."""
from __future__ import annotations
import argparse
import contextlib
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import common_three_arm as common

load, dump, sha = common.load, common.dump, common.sha


def dynamic_schedule(work, sources):
    schedule = common.build_schedule(work)
    for unit in schedule:
        w = next(w for w in work if w['question_id'] == unit['question_id'])
        unit['planned_max_attempts'] = (3 if unit['arm'] == 'P0' else
            (len(w['chunks']) + 1 if w['resolution']['status'] == 'RESOLVED' else 0)
            if unit['arm'] == 'A' else len(sources[unit['source_id']]['chunks']) + 1)
    return schedule


def validate_questions(questions, sid):
    if not 1 <= len(questions) <= 2:
        raise ValueError('每源须1至2题')
    ids = set()
    for q in questions:
        if set(q) != {'question_id', 'source_id', 'question', 'range_condition'}:
            raise ValueError('问题字段不符合契约')
        if q['source_id'] != sid or not isinstance(q['question'], str) or not q['question'].strip():
            raise ValueError('问题来源或文本无效')
        if q['question_id'] in ids or not safe_id(q['question_id']):
            raise ValueError('问题标识重复或不安全')
        ids.add(q['question_id'])


def safe_id(value):
    return isinstance(value, str) and 0 < len(value) <= 100 and all(c.isascii() and (c.isalnum() or c in '_-') for c in value)


def copy_runtime(frozen, runtime):
    snapshot = load(frozen / 'snapshot.json')
    common.verify_files(frozen, snapshot['files'])
    runtime.mkdir(parents=True, exist_ok=False)
    for relative in snapshot['files']:
        target = common.contained(runtime, runtime / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(common.contained(frozen, frozen / relative), target)
    files = dict(snapshot['files'])
    for origin in (Path(common.__file__), Path(__file__)):
        relative = 'backend/research/' + origin.name
        shutil.copyfile(origin, runtime / relative)
        files[relative] = sha(runtime / relative)
    for directory in ('backend/output/kg', 'backend/uploads', 'artifacts', 'temp', 'cache', 'public_sources', 'home/AppData/Roaming', 'home/AppData/Local'):
        (runtime / directory).mkdir(parents=True, exist_ok=True)
    dump(runtime / 'snapshot.json', {**snapshot, 'run_root':str(runtime), 'files':files})
    return files


def verify_registration(profile):
    profile = Path(profile).resolve()
    reg = load(profile / 'registration.json')
    if sha(profile / 'registration.json') != load(profile / 'registration.sha256.json')['registration_sha256']:
        raise ValueError('登记漂移')
    common.verify_files(Path(reg['runtime']), reg['source_code_files'])
    common.verify_files(Path(reg['runtime']), {s['file']:s['sha256'] for s in reg['sources'].values()})
    if sha(Path(reg['runtime']) / 'snapshot.json') != reg['runtime_snapshot_sha256']:
        raise ValueError('源码快照漂移')
    if common.environment_identity() != reg['environment']:
        raise ValueError('依赖身份漂移')
    for p, expected in reg['governance_sha256'].items():
        if sha(p) != expected: raise ValueError('输入或契约漂移')
    assets = profile / 'execution-assets.json'
    if assets.exists():
        if sha(assets) != load(profile / 'execution-assets.sha256.json')['sha256']:
            raise ValueError('索引收据漂移')
        common.verify_files(Path(reg['runtime']), load(assets)['kg_files'])
        if sha(profile/'index-calls/ledger.json')!=load(assets)['index_ledger_sha256']:
            raise ValueError('索引费用收据漂移')
    return reg


def preflight(profile):
    """Fresh-process only: native extraction SDK MockTransport, then resolver."""
    profile = Path(profile).resolve()
    spec = load(profile / 'prepare-input.json')
    from research.development_isolation import activate, preflight_sources
    activate(spec['runtime'])
    result = preflight_sources(spec['runtime'], spec['manifest'], spec['xml'])
    from research.scope_v2 import Source, assemble_scope
    from research.development_structure import StructureIndex, StructureNode
    from research.development_scope import resolve_development_scope
    record = load(spec['manifest'])[0]
    canonical = (Path(spec['manifest']).parent / record['canonical_file']).resolve()
    text = canonical.read_bytes().decode('utf-8')
    structure = result['sources'][0]['bridge']['structure']
    index = StructureIndex(structure['source_id'], structure['source_sha256'], tuple(StructureNode(**n) for n in structure['nodes']), structure['metadata'])
    source = Source(record['source_id'], text)
    work = []
    for q in load(spec['questions']):
        resolution = resolve_development_scope(q['question'], [source], [index])
        assembly = assemble_scope(resolution, [source], max_bytes=120000)
        chunks = []
        if assembly.status == 'COMPLETE_SCOPE':
            for mapping in assembly.mappings:
                for offset in range(mapping['start'], mapping['end'], 8000):
                    end = min(offset + 8000, mapping['end'])
                    chunks.append({'source_id':source.key, 'start':offset, 'end':end, 'chunk_id':f'{source.key}-A-{offset}-{end}'})
        work.append({**q,'resolution':asdict(resolution),'assembly':asdict(assembly),'chunks':chunks})
    dump(profile / 'prepared-structure.json', {'preflight_sha256':sha(Path(spec['runtime'])/'artifacts/preflight.json'), 'structure':structure,'work':work})


def wire_bytes(messages):
    import requests
    return len(requests.Request('POST', 'https://api.deepseek.com/chat/completions', json={
        'model':'deepseek-flash','temperature':0.0,'thinking':{'type':'disabled'},'max_tokens':2048,'messages':messages}).prepare().body)


def prepare(batch_file, frozen, prompt_profile, root):
    batch_file, frozen, prompt_profile, root = map(lambda p:Path(p).resolve(), (batch_file,frozen,prompt_profile,root))
    batch = load(batch_file)
    data_governance={}
    freeze=batch_file.parent/'freeze.json'
    independent=batch_file.parent/'independent-data-review.json'
    data_verified=False
    if freeze.exists():
        for item in load(freeze)['files']:
            p=common.contained(batch_file.parent,batch_file.parent/item['path'])
            if p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:raise ValueError('数据冻结hash不符')
            data_governance[str(p)]=item['sha256']
        for p in (freeze,independent,batch_file.parent/'independent-data-review.md'):
            data_governance[str(p)]=sha(p)
        data_verified=True
    entries = batch['sources']
    if not 1 <= len(entries) <= 3 or len({e['source_id'] for e in entries}) != len(entries):
        raise ValueError('须1至3份独立来源')
    prompt = common.verify_registration(prompt_profile)
    root.mkdir(parents=True, exist_ok=False)
    records=[]
    for entry in entries:
        sid = entry['source_id']
        if not safe_id(sid): raise ValueError('来源标识不安全')
        paths={name:(batch_file.parent / entry[name]).resolve() for name in ('manifest_file','xml_file','questions_file')}
        manifest=load(paths['manifest_file'])
        if len(manifest)!=1 or manifest[0]['source_id']!=sid:raise ValueError('必须单源manifest')
        record=manifest[0]
        sourcepaths={name:(paths['manifest_file'].parent/record[name]).resolve() for name in ('raw_file','canonical_file','section_or_page_map')}
        if sourcepaths['raw_file'].suffix.lower()!='.pdf':raise ValueError('仅PDF')
        if sha(sourcepaths['raw_file'])!=record['source_sha256'] or sha(sourcepaths['canonical_file'])!=record['canonical_sha256']:raise ValueError('来源hash不符')
        text=sourcepaths['canonical_file'].read_bytes().decode('utf-8')
        if not 0<len(text)<=56000:raise ValueError('来源超预登记长度')
        questions=load(paths['questions_file']);validate_questions(questions,sid)
        profile=root/sid;runtime=profile/'runtime';files=copy_runtime(frozen,runtime)
        target=runtime/'public_sources'/f'{sid}.txt';shutil.copyfile(sourcepaths['canonical_file'],target)
        spec={'runtime':str(runtime),'manifest':str(paths['manifest_file']),'xml':str(paths['xml_file']),'questions':str(paths['questions_file'])}
        dump(profile/'prepare-input.json',spec)
        command=[sys.executable,'-B',str(runtime/'backend/research/new_document_pilot.py'),'preflight','--root',str(profile)]
        completed=subprocess.run(command,capture_output=True,timeout=300)
        dump(profile/'preflight-process.json',{'exit_code':completed.returncode,'stdout_sha256':hashlib.sha256(completed.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(completed.stderr).hexdigest()})
        if completed.returncode:raise RuntimeError('原生SDK离线预检失败')
        prepared=load(profile/'prepared-structure.json');pf=load(runtime/'artifacts/preflight.json')
        attempts=2*pf['planned_requests']+4;indexbytes=2*pf['planned_input_bytes']+24000
        sources={sid:{'file':str(target.relative_to(runtime)).replace('\\','/'),'sha256':sha(target),'chunks':common.scan_chunks(sid,text),'unicode_characters':len(text)}}
        schedule=dynamic_schedule(prepared['work'],sources);bound=sum(u['planned_max_attempts'] for u in schedule)
        governance={str(p):sha(p) for p in [batch_file,*paths.values(),*sourcepaths.values(),profile/'prepare-input.json',profile/'prepared-structure.json',runtime/'artifacts/preflight.json',prompt_profile/'registration.json']}
        repo=Path(common.__file__).resolve().parents[2]
        for rel in ('docs/contracts/2026-10-16-new-document-pilot.md','docs/plans/2026-10-16-new-document-pilot.md','docs/review/2026-10-16-new-document-pilot-design-review.md'):
            governance[str(repo/rel)]=sha(repo/rel)
        reg={'status':'REGISTERED_NOT_EXECUTED','runtime':str(runtime),'source_id':sid,'source_code_files':files,'runtime_snapshot_sha256':sha(runtime/'snapshot.json'),'environment':common.environment_identity(),'governance_sha256':governance,'sources':sources,'heading_structures':{sid:{'structure':prepared['structure']}},'work':prepared['work'],'schedule':schedule,'global_path_attempts':bound,'global_seconds':min(5400,120*len(schedule)),'common_budget':prompt['common_budget'],'model_config':prompt['model_config'],'kg_files':{},'path_proof':common.prove_p0_path(frozen),'gold_loaded':False,'scientific_stage':'M2_OPEN','manifest':spec['manifest'],'xml':spec['xml'],'index_budget':{'attempts':attempts,'input_bytes':indexbytes,'seconds':1800,'single_input_bytes':24000,'single_actual_prompt_tokens':8192,'actual_prompt_tokens':8192*attempts,'actual_completion_tokens':4096*attempts},**{k:prompt[k] for k in ('system_prompt','map_instruction','reduce_instruction')}}
        wire=[]
        index=[{'heading':n['title'],'start':n['start'],'end':n['end']} for n in prepared['structure']['nodes'] if n['kind']=='heading']
        for unit in schedule:
            if unit['arm']=='P0' or not unit['planned_max_attempts']:continue
            w=next(w for w in prepared['work'] if w['question_id']==unit['question_id'])
            for c in w['chunks'] if unit['arm']=='A' else sources[sid]['chunks']:
                body=reg['map_instruction']+'\n[QUESTION]\n'+w['question']+'\n[STRUCTURE INDEX]\n'+json.dumps(index,ensure_ascii=False)+f"\n[CHUNK {c['chunk_id']}; source {sid}; Unicode [{c['start']},{c['end']})]\n"+text[c['start']:c['end']]
                size=wire_bytes([{'role':'system','content':reg['system_prompt']},{'role':'user','content':body}]);wire.append(size)
        if wire and max(wire)>24000:raise ValueError('map单请求超共同字节限额')
        reg['offline_map_wire_bytes']=wire
        reg['common_budget']={**reg['common_budget'],'global_path_attempts':bound,'global_seconds':reg['global_seconds']}
        reg['governance_sha256'].update(data_governance)
        reg['data_freeze_verified']=data_verified
        dump(profile/'registration.json',reg);dump(profile/'registration.sha256.json',{'registration_sha256':sha(profile/'registration.json')});verify_registration(profile)
        records.append({'source_id':sid,'profile':str(profile),'registration_sha256':sha(profile/'registration.json'),'units':len(schedule),'generation_attempts':bound,'generation_seconds':reg['global_seconds'],'index_budget':reg['index_budget']})
    receipt={'status':'REGISTERED_NOT_EXECUTED','sources':records,'total_units':sum(r['units'] for r in records),'total_generation_attempts':sum(r['generation_attempts'] for r in records),'total_index_attempts':sum(r['index_budget']['attempts'] for r in records),'total_seconds':sum(r['generation_seconds']+1800 for r in records),'gold_loaded':False}
    dump(root/'batch-registration.json',receipt);dump(root/'batch-registration.sha256.json',{'sha256':sha(root/'batch-registration.json')})
    return receipt


def index_guard_class(cap):
    from research.development_budget import BudgetGuard,BudgetLimits,BudgetStopped
    class IndexGuard(BudgetGuard):
        @contextlib.contextmanager
        def phase(self,name,question_id=None):
            with super().phase(name,question_id):
                self.phase_deadline=self.state['started_epoch']+cap['seconds'];yield self
        def _begin(self,url,raw,transport):
            if len(raw)>cap['single_input_bytes']:self._reject('索引单次字节超额')
            return super()._begin(url,raw,transport)
        def _finish(self,record,status,raw):
            super()._finish(record,status,raw)
            usages=[r['usage'] for r in self.state['records'] if r.get('usage')]
            if record['usage']['prompt_tokens']>8192 or sum(u['prompt_tokens'] for u in usages)>cap['actual_prompt_tokens'] or sum(u['completion_tokens'] for u in usages)>cap['actual_completion_tokens']:
                self._reject('索引实际token超额，已保留费用')
    return IndexGuard


def index_worker(profile):
    profile=Path(profile).resolve();reg=verify_registration(profile)
    if (profile/'execution-assets.json').exists() or (profile/'index-calls').exists():raise ValueError('禁止重放索引')
    from research.development_isolation import activate,index_sources
    activate(reg['runtime'])
    from research.development_budget import BudgetLimits
    cap=reg['index_budget'];IndexGuard=index_guard_class(cap)
    guard=IndexGuard(profile/'index-calls',os.environ.get('LANGEXTRACT_API_KEY',''),BudgetLimits(total_attempts=cap['attempts'],index_attempts=cap['attempts'],p0_attempts=0,a_attempts=0,input_bytes=cap['input_bytes'],window_seconds=cap['seconds']))
    with guard.install():result=index_sources(reg['runtime'],reg['manifest'],reg['xml'],guard)
    if not result or result[0]['nodes']==0:raise RuntimeError('CORPUS_UNAVAILABLE')
    runtime=Path(reg['runtime']);kg={str(p.relative_to(runtime)).replace('\\','/'):sha(p) for p in (runtime/'backend/output/kg'/reg['source_id']).glob('*.json')}
    store=runtime/'backend/output/docs_store.json';kg[str(store.relative_to(runtime)).replace('\\','/')]=sha(store)
    dump(profile/'execution-assets.json',{'kg_files':kg,'index_ledger_sha256':sha(profile/'index-calls/ledger.json'),'result':result})
    dump(profile/'execution-assets.sha256.json',{'sha256':sha(profile/'execution-assets.json')})


def worker(profile,unit_id,deadline,remaining):
    reg=verify_registration(profile);unit=next(u for u in reg['schedule'] if u['unit_id']==unit_id)
    if unit['arm']=='A' and unit['planned_max_attempts']==0:
        row={**unit,'status':'UNRESOLVED','answer':None,'actual_attempts':0,'semantic_scoring':'NOT_ASSESSABLE'}
        dump(Path(profile)/'out/units'/unit_id/'result.json',row);return row
    if not (Path(profile)/'execution-assets.json').exists():raise ValueError('缺少索引冻结收据')
    common.verify_registration=verify_registration
    return common.run_worker(profile,unit_id,deadline,remaining)


def process(command,reg,key,seconds,receipt):
    completed=subprocess.run(command,env=common.child_environment(reg['runtime'],key),cwd=reg['runtime'],capture_output=True,timeout=seconds)
    dump(receipt,{'exit_code':completed.returncode,'stdout_sha256':hashlib.sha256(completed.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(completed.stderr).hexdigest(),'raw_output_omitted':True})
    return completed.returncode


def run(root,env_file):
    root=Path(root).resolve()
    batch=load(root/'batch-registration.json')
    if sha(root/'batch-registration.json')!=load(root/'batch-registration.sha256.json')['sha256']:raise ValueError('批次登记漂移')
    if (root/'run-started.json').exists():raise ValueError('禁止续跑或重放pilot')
    for source in batch['sources']:
        source_reg=verify_registration(source['profile'])
        if not source_reg.get('data_freeze_verified'):raise ValueError('缺少独立数据冻结登记')
        if sha(Path(source['profile'])/'registration.json')!=source['registration_sha256']:raise ValueError('源登记漂移')
    from dotenv import dotenv_values
    key=dotenv_values(env_file).get('LANGEXTRACT_API_KEY')
    if not key:raise ValueError('缺少授权API密钥')
    dump(root/'run-started.json',{'epoch':time.time()})
    stopped=False;all_rows=[]
    for source in batch['sources']:
        profile=Path(source['profile']);reg=verify_registration(profile);runner=Path(reg['runtime'])/'backend/research/new_document_pilot.py'
        base=[sys.executable,'-B','-X','utf8',str(runner)]
        corpus_failed=False
        if not stopped:
            try:stopped=bool(process(base+['index','--root',str(profile)],reg,key,1800,profile/'index-process.json'))
            except subprocess.TimeoutExpired:stopped=True;dump(profile/'index-process.json',{'status':'PROFILE_STOP','reason':'索引超时远端费用未知'})
            corpus_failed=stopped
        started=time.time();attempts=0
        for unit in reg['schedule']:
            row={**unit,'status':'CORPUS_UNAVAILABLE' if corpus_failed else 'NOT_RUN','answer':None,'actual_attempts':0}
            remaining=reg['global_path_attempts']-attempts
            timeleft=reg['global_seconds']-(time.time()-started)
            if not stopped and timeleft>0 and remaining>=unit['planned_max_attempts']:
                deadline=time.time()+min(120,timeleft)
                try:
                    code=process(base+['worker','--root',str(profile),'--unit-id',unit['unit_id'],'--deadline',str(deadline),'--remaining',str(remaining)],reg,key,min(120,timeleft),profile/'out/process'/f"{unit['unit_id']}.json")
                    result=profile/'out/units'/unit['unit_id']/'result.json'
                    row=load(result) if result.exists() else {**row,'status':'PROFILE_STOP'}
                    if code:row.update(status='PROFILE_STOP',answer=None)
                except subprocess.TimeoutExpired:row.update(status='PROFILE_STOP',answer=None,reason='超时，远端费用未知')
                ledger=profile/'out/units'/unit['unit_id']/'calls/ledger.json'
                if ledger.exists():
                    state=load(ledger);row['actual_attempts']=state['actual_attempts']
                    row['usage']={'prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens',0) for r in state['records']),'completion_tokens':sum(r.get('usage',{}).get('completion_tokens',0) for r in state['records']),'unknown_cost_requests':sum(r.get('cost_status')=='UNKNOWN' for r in state['records'])}
                    if row['usage']['unknown_cost_requests'] or any(r['status']=='SENT_PENDING' for r in state['records']):row.update(status='PROFILE_STOP',answer=None)
                attempts+=row.get('actual_attempts',0)
                if attempts>reg['global_path_attempts']:row.update(status='PROFILE_STOP',answer=None)
                if row['status']=='PROFILE_STOP':stopped=True
            dump(profile/'out/units'/unit['unit_id']/'result.json',row);all_rows.append(row)
            dump(root/'pilot-status.json',{'status':'STOPPED' if stopped else 'RUNNING','units':all_rows,'registered_units':batch['total_units']})
    dump(root/'pilot-status.json',{'status':'STOPPED' if stopped else 'FINISHED','units':all_rows,'registered_units':batch['total_units'],'gold_loaded':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','preflight','index','worker','run'))
    for field in ('root','batch','frozen','prompt-profile','env-file','unit-id'):parser.add_argument('--'+field)
    parser.add_argument('--deadline',type=float);parser.add_argument('--remaining',type=int)
    args=parser.parse_args()
    if args.mode=='prepare':prepare(args.batch,args.frozen,args.prompt_profile,args.root)
    elif args.mode=='preflight':preflight(args.root)
    elif args.mode=='index':index_worker(args.root)
    elif args.mode=='worker':worker(args.root,args.unit_id,args.deadline,args.remaining)
    else:run(args.root,args.env_file)

if __name__=='__main__':main()
