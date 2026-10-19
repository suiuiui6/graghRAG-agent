"""Registered, bounded public-development three-arm runner.

Offline: prepare --frozen-runtime PATH --inputs PATH --profile-root NEW_PATH
Authorized execution only: run --profile-root PATH --env-file PATH
Internal child: worker --profile-root PATH --unit-id ID
The runtime and KG are copied from the historical executed snapshot, never from
current production sources. No Gold is opened. The env file is opened only by
the explicitly requested run command, never by prepare or a child.
"""
from __future__ import annotations
import argparse
import ast
import contextlib
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


class ResourceCap(RuntimeError):
    pass


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.pending')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root,path):
    root,path=Path(root).resolve(),Path(path).resolve()
    if path==root or not path.is_relative_to(root):raise ValueError('路径越出新隔离根')
    return path


def verify_files(root,files):
    for relative,expected in files.items():
        path=contained(root,Path(root)/relative)
        if sha(path)!=expected:raise ValueError('已登记文件发生漂移')


def build_schedule(work):
    result=[]
    for qi,w in enumerate(work):
        for repeat in range(1,4):
            arms=('P0','A','S'); rotation=(qi+repeat-1)%3
            for arm in arms[rotation:]+arms[:rotation]:
                result.append({'unit_id':f"{w['question_id']}-r{repeat}-{arm}",'question_id':w['question_id'],
                               'source_id':w['source_id'],'repeat':repeat,'arm':arm,'sequence':len(result)+1})
    return result


def scan_chunks(source_id,text):
    return [{'source_id':source_id,'start':start,'end':min(start+8000,len(text)),
             'chunk_id':f'{source_id}-S-{start}-{min(start+8000,len(text))}'} for start in range(0,len(text),8000)]


def prove_p0_path(root):
    """Fail if the frozen scoped call graph no longer matches the audited bound."""
    root=Path(root);files={};trees={}
    for name in ('generator.py','retrieval.py','routes/rag_query.py','config.py','models.py','research/development_isolation.py'):
        path=root/'backend'/name;files[name]=sha(path);trees[name]=ast.parse(path.read_text(encoding='utf-8-sig'))
    def function(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    def calls(node,name):return [n for n in ast.walk(node) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id==name) or (isinstance(n.func,ast.Attribute) and n.func.attr==name))]
    preprocess=function(trees['retrieval.py'],'preprocess_query')
    posts=calls(preprocess,'post');assert len(posts)==1
    assert not any(isinstance(n,(ast.For,ast.While)) and posts[0] in list(ast.walk(n)) for n in ast.walk(preprocess))
    generator=function(trees['generator.py'],'generate_answer');assert len(calls(generator,'_post_with_bounded_retries'))==1
    assert len(calls(function(trees['generator.py'],'generate'),'generate_answer'))==1
    bounded=function(trees['generator.py'],'_post_with_bounded_retries');assert len(calls(bounded,'post'))==1
    attempts=next(n for n in bounded.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='attempts' for t in n.targets))
    assert ast.unparse(attempts.value)=='max(0, int(config.max_retries)) + 1'
    cfg=next(n for n in ast.walk(trees['generator.py']) if isinstance(n,ast.ClassDef) and n.name=='GenerationConfig')
    retries=next(n.value.value for n in cfg.body if isinstance(n,ast.AnnAssign) and n.target.id=='max_retries');assert retries==1
    scoped=function(trees['routes/rag_query.py'],'_generate_scoped_rag')
    configs=calls(scoped,'GenerationConfig');assert len(configs)==1 and 'max_retries' not in {k.arg for k in configs[0].keywords}
    pipelines=calls(scoped,'RetrievalPipeline');assert len(pipelines)==1
    assert not {'query_optimizer','domain_dict'} & {k.arg for k in pipelines[0].keywords}
    constructor=function(next(n for n in ast.walk(trees['retrieval.py']) if isinstance(n,ast.ClassDef) and n.name=='RetrievalPipeline'),'__init__')
    defaults=dict(zip([a.arg for a in constructor.args.args][-len(constructor.args.defaults):],constructor.args.defaults))
    assert all(isinstance(defaults[n],ast.Constant) and defaults[n].value is None for n in ('query_optimizer','domain_dict'))
    assert len(calls(scoped,'generate'))==1
    retrieve=function(next(n for n in ast.walk(trees['retrieval.py']) if isinstance(n,ast.ClassDef) and n.name=='RetrievalPipeline'),'retrieve')
    # retrieve delegates to _retrieve_impl; actual preprocess exists exactly once.
    assert len(calls(trees['retrieval.py'],'preprocess_query'))==1
    global_default=next(n for n in trees['config.py'].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFAULT_ENABLE_GLOBAL_MODE' for t in n.targets))
    assert isinstance(global_default.value,ast.Constant) and global_default.value.value is False
    opts=next(n for n in ast.walk(trees['models.py']) if isinstance(n,ast.ClassDef) and n.name=='QueryOptions')
    global_field=next(n for n in opts.body if isinstance(n,ast.AnnAssign) and n.target.id=='enable_global_mode')
    assert any(k.arg=='default' and isinstance(k.value,ast.Name) and k.value.id=='DEFAULT_ENABLE_GLOBAL_MODE' for k in global_field.value.keywords)
    query=function(trees['research/development_isolation.py'],'query_source')
    assert all(k.arg!='enable_global_mode' for c in calls(query,'QueryOptions') for k in c.keywords)
    return {'status':'STATIC_SCOPED_PATH_SUPPORTED','preprocess_attempts':1,'generation_attempts':2,
            'per_unit_max_attempts':3,'enable_global_mode':False,'source_sha256':files,
            'locators':{'preprocess':preprocess.lineno,'generation_retry':bounded.lineno,'scoped_route':scoped.lineno},
            'reason':'Scoped KG route has no optimizer/domain model; one preprocess POST plus one generation site with max_retries=1; citation notice only appends text.'}


def unit_guard_class():
    """Import the effective frozen transport only after worker activation."""
    from research.development_budget import BudgetGuard, BudgetLimits, BudgetStopped
    class CommonUnitGuard(BudgetGuard):
        def __init__(self,artifact_dir,key,arm,planned_calls,deadline=None,global_attempts_remaining=177):
            self.arm=arm;self.planned_calls=planned_calls
            self.global_attempts_remaining=global_attempts_remaining
            self.unit_deadline=deadline or time.time()+120
            super().__init__(artifact_dir,key,BudgetLimits(total_attempts=8,index_attempts=0,p0_attempts=8,a_attempts=8,input_bytes=192000,window_seconds=120))
        def _reject(self,reason):
            self.state['stop_kind']='PROFILE_STOP';super()._reject(reason)
        def resource_stop(self,reason):
            self.state.update(closed=True,stop_kind='RESOURCE_CAP',stop_reason=reason)
            self.state['records'].append({'status':'NOT_SENT','phase':self.phase_name,'question_id':self.question_id,'reason':reason})
            self._save();raise ResourceCap(reason)
        @contextlib.contextmanager
        def phase(self,name,question_id=None):
            with super().phase(name,question_id):
                self.phase_deadline=self.unit_deadline
                yield self
        def _begin(self,url,raw,transport):
            if self.closed:
                if self.state.get('stop_kind')=='RESOURCE_CAP':raise ResourceCap('单元资源限额已关闭')
                return super()._begin(url,raw,transport)
            if time.time()>=self.unit_deadline:self._reject('单元墙钟耗尽，停止profile')
            if self.actual_attempts>=self.global_attempts_remaining:self._reject('全组剩余请求额度耗尽，未发送')
            if self.actual_attempts>=8:self.resource_stop('单元8次实际HTTP尝试上限')
            if self.actual_attempts>=self.planned_calls:self._reject('请求超过已证明原生路径上限')
            if len(raw)>24000 or self.state['input_bytes']+len(raw)>192000:self.resource_stop('请求输入字节达到共同限额')
            try:data=json.loads(raw)
            except (ValueError,TypeError):return super()._begin(url,raw,transport)
            if not isinstance(data,dict) or type(data.get('temperature')) not in (int,float) or data['temperature']!=0.0:self._reject('共同temperature必须0.0')
            if data.get('max_tokens') not in ({300,2048} if self.arm=='P0' else {2048}):self._reject('共同输出声明不符')
            record,timeout=super()._begin(url,raw,transport);record['arm']=self.arm;self._save()
            return record, min(timeout,max(.001,self.unit_deadline-time.time()))
        def _finish(self,record,status,raw):
            try:super()._finish(record,status,raw)
            except BudgetStopped:
                self.state['stop_kind']='PROFILE_STOP';self._save();raise
            usages=[r['usage'] for r in self.state['records'] if r.get('usage')]
            if record['usage']['prompt_tokens']>8192 or sum(u['prompt_tokens'] for u in usages)>65536 or sum(u['completion_tokens'] for u in usages)>16384:
                self.resource_stop('实际usage超过共同token限额，已保留费用')
        def _failed(self,record):
            super()._failed(record);self.state['stop_kind']='PROFILE_STOP';self._save()
    return CommonUnitGuard


def environment_identity():
    packages=('openai','requests','httpx','httpx2','langextract','pydantic','networkx')
    return {p:importlib.metadata.version(p) for p in packages}


def child_environment(runtime,key):
    runtime=Path(runtime).resolve()
    allow=('SystemRoot','WINDIR','PATH','PATHEXT','COMSPEC','NUMBER_OF_PROCESSORS',
           'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','SSL_CERT_DIR')
    env={k:os.environ[k] for k in allow if k in os.environ}
    env.update(LANGEXTRACT_API_KEY=key,LANGEXTRACT_MODEL_ID='deepseek-flash',LANGEXTRACT_BASE_URL='https://api.deepseek.com',
        LANGEXTRACT_TEMPERATURE='0.0',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',HF_ENDPOINT='https://huggingface.co',
        HOME=str(runtime/'home'),USERPROFILE=str(runtime/'home'),APPDATA=str(runtime/'home/AppData/Roaming'),
        LOCALAPPDATA=str(runtime/'home/AppData/Local'),TMP=str(runtime/'temp'),TEMP=str(runtime/'temp'),TMPDIR=str(runtime/'temp'),
        HF_HOME=str(runtime/'cache'),XDG_CACHE_HOME=str(runtime/'cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    return env


def prepare(frozen_runtime,inputs_path,profile_root):
    frozen,profile=Path(frozen_runtime).resolve(),Path(profile_root).resolve()
    if frozen.is_relative_to(profile) or profile.is_relative_to(frozen):raise ValueError('新profile不能与冻结运行根重叠')
    old_snapshot=load(frozen/'snapshot.json');verify_files(frozen,old_snapshot['files'])
    prepared=load(inputs_path)
    for p,h in prepared['input_hashes'].items():
        if sha(p)!=h:raise ValueError('公开来源漂移')
    if sha(Path(prepared['data_dir'])/'questions.input.json')!=prepared['questions_sha256']:raise ValueError('问题输入漂移')
    if len(prepared['work'])!=6 or {w['source_id'] for w in prepared['work']}!={'LCNC-HOME','NIST-8091'}:raise ValueError('只准六题两公开源')
    proof=prove_p0_path(frozen)
    repo=Path(__file__).resolve().parents[2]
    governance={str(repo/'docs/contracts/2026-10-15-common-three-arm-evaluation.md'):sha(repo/'docs/contracts/2026-10-15-common-three-arm-evaluation.md'),
                str(repo/'docs/plans/2026-10-15-common-three-arm-evaluation.md'):sha(repo/'docs/plans/2026-10-15-common-three-arm-evaluation.md')}
    profile.mkdir(parents=True,exist_ok=False);runtime=profile/'runtime';runtime.mkdir()
    for relative,expected in old_snapshot['files'].items():
        target=contained(runtime,runtime/relative);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(contained(frozen,frozen/relative),target)
    runner=runtime/'backend/research/common_three_arm.py';shutil.copyfile(Path(__file__),runner)
    snapshot={**old_snapshot,'run_root':str(runtime),'files':{**old_snapshot['files'],'backend/research/common_three_arm.py':sha(runner)}}
    dump(runtime/'snapshot.json',snapshot)
    for directory in ('temp','cache','artifacts','backend/output/kg','public_sources','home/AppData/Roaming','home/AppData/Local'):(runtime/directory).mkdir(parents=True,exist_ok=True)
    kg_files={}
    kg_provenance={}
    for source in ('LCNC-HOME','NIST-8091'):
        for p in (frozen/'backend/output/kg'/source).glob('*.json'):
            archived=repo/'docs/review/development-budget-20261014/executed-isolation/kg'/source/p.name
            if sha(p)!=sha(archived):raise ValueError('运行KG与冻结归档不一致')
            kg_provenance[str(archived)]=sha(archived)
            rel=p.relative_to(frozen);target=contained(runtime,runtime/rel);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);kg_files[str(rel).replace('\\','/')]=sha(target)
    docs=load(frozen/'backend/output/docs_store.json')
    if {d['document_id'] for d in docs}!={'LCNC-HOME','NIST-8091'}:raise ValueError('冻结文档库不匹配公开两源')
    for doc in docs:doc['kg_path']=str(runtime/'backend/output/kg'/doc['document_id'])
    dump(runtime/'backend/output/docs_store.json',docs)
    kg_files['backend/output/docs_store.json']=sha(runtime/'backend/output/docs_store.json')
    source_records=load(Path(prepared['data_dir'])/'sources.json');sources={}
    for r in source_records:
        original=Path(prepared['data_dir'])/r['canonical_file'];target=runtime/'public_sources'/f"{r['source_id']}.txt"
        shutil.copyfile(original,target);text=target.read_bytes().decode('utf-8')
        if sha(target)!=r['canonical_sha256']:raise ValueError('复制规范文本hash不符')
        sources[r['source_id']]={'file':str(target.relative_to(runtime)).replace('\\','/'),'sha256':sha(target),
                                'chunks':scan_chunks(r['source_id'],text),'unicode_characters':len(text)}
    schedule=build_schedule(prepared['work']);a=sum(len(w['chunks'])+1 for w in prepared['work']);s=sum(len(sources[w['source_id']]['chunks'])+1 for w in prepared['work'])
    if (a,s)!=(14,27):raise ValueError('实际A/S调用计划不等于已批准14/27')
    for unit in schedule:
        w=next(w for w in prepared['work'] if w['question_id']==unit['question_id'])
        unit['planned_max_attempts']=3 if unit['arm']=='P0' else len(w['chunks'] if unit['arm']=='A' else sources[unit['source_id']]['chunks'])+1
    bound=sum(u['planned_max_attempts'] for u in schedule)
    if bound!=177:raise ValueError('全组路径上限未证明177')
    registration={'status':'REGISTERED_NOT_EXECUTED','runtime':str(runtime),'frozen_runtime':str(frozen),
        'frozen_snapshot_sha256':sha(frozen/'snapshot.json'),'runtime_snapshot_sha256':sha(runtime/'snapshot.json'),
        'source_code_files':snapshot['files'],'kg_files':kg_files,'sources':sources,'work':prepared['work'],
        'system_prompt':prepared['system_prompt'],'map_instruction':prepared['map_instruction'],'reduce_instruction':prepared['reduce_instruction'],
        'heading_structures':prepared['sources'],'inputs_sha256':sha(inputs_path),'schedule':schedule,'path_proof':proof,
        'A_calls_per_round':a,'S_calls_per_round':s,'global_path_attempts':bound,'global_seconds':5400,
        'environment':environment_identity(),'governance_sha256':governance,'kg_provenance_sha256':kg_provenance,
        'model_config':{'model':'deepseek-flash','temperature':0.0,'thinking':'disabled','stream':False,'max_tokens':2048,'p0_preprocess_max_tokens':300,'p0_enable_global_mode':False},
        'common_budget':{'attempts_per_unit':8,'single_input_json_utf8_bytes':24000,'unit_input_json_utf8_bytes':192000,'unit_seconds_including_startup':120,
          'single_actual_prompt_tokens':8192,'unit_actual_prompt_tokens':65536,'unit_actual_completion_tokens':16384,'global_seconds':5400,'global_path_attempts':177},
        'gold_loaded':False,'scientific_stage':'M2_OPEN'}
    dump(profile/'registration.json',registration)
    dump(profile/'registration.sha256.json',{'registration_sha256':sha(profile/'registration.json')})
    return registration


def verify_registration(profile):
    profile=Path(profile).resolve();reg=load(profile/'registration.json')
    if sha(profile/'registration.json')!=load(profile/'registration.sha256.json')['registration_sha256']:raise ValueError('登记文件漂移')
    runtime=contained(profile,reg['runtime'])
    verify_files(runtime,reg['source_code_files']);verify_files(runtime,reg['kg_files'])
    verify_files(runtime,{s['file']:s['sha256'] for s in reg['sources'].values()})
    if sha(runtime/'snapshot.json')!=reg['runtime_snapshot_sha256']:raise ValueError('runtime snapshot漂移')
    if environment_identity()!=reg['environment']:raise ValueError('执行依赖身份不一致')
    for mapping in ('governance_sha256','kg_provenance_sha256'):
        for path,expected in reg[mapping].items():
            if sha(path)!=expected:raise ValueError('契约/计划或历史KG归档发生漂移')
    return reg


def clear_unit_cache(profile,registration):
    runtime=contained(profile,registration['runtime'])
    for suffix in ('','-wal','-shm','-journal'):
        path=contained(runtime,runtime/'backend/output'/('rewrite-cache.sqlite3'+suffix))
        if path.exists():
            if path.is_dir():raise ValueError('缓存清理路径不是文件')
            path.unlink()


def resolve_a_work(work,registration,text):
    from research.scope_v2 import Source,assemble_scope
    from research.development_structure import StructureIndex,StructureNode
    from research.development_scope import resolve_development_scope
    started=time.monotonic();spec=registration['heading_structures'][work['source_id']]['structure']
    index=StructureIndex(spec['source_id'],spec['source_sha256'],tuple(StructureNode(**n) for n in spec['nodes']),spec['metadata'])
    source=Source(work['source_id'],text)
    resolution=resolve_development_scope(work['question'],[source],[index]);assembly=assemble_scope(resolution,[source],max_bytes=120000)
    actual_resolution=json.loads(json.dumps(asdict(resolution)))
    chunks=[]
    for mapping in assembly.mappings:
        for offset in range(mapping['start'],mapping['end'],8000):
            end=min(offset+8000,mapping['end']);sid=work['source_id']
            chunks.append({'source_id':sid,'start':offset,'end':end,'chunk_id':f'{sid}-A-{offset}-{end}'})
    if assembly.status!='COMPLETE_SCOPE' or actual_resolution!=work['resolution'] or chunks!=work['chunks']:raise ValueError('自动范围重算与预登记不一致')
    return {**work,'resolution':actual_resolution,'chunks':chunks,'local_resolution_seconds':time.monotonic()-started}


def map_reduce(unit,work,registration,guard,text):
    import requests
    arm=unit['arm']
    if arm=='A':work=resolve_a_work(work,registration,text)
    chunks=work['chunks'] if arm=='A' else registration['sources'][unit['source_id']]['chunks']
    index=[{'heading':n['title'],'start':n['start'],'end':n['end']} for n in registration['heading_structures'][unit['source_id']]['structure']['nodes'] if n['kind']=='heading']
    def call(messages):
        with guard.phase('a',unit['question_id']):
            reply=requests.post('https://api.deepseek.com/chat/completions',headers={'Authorization':'Bearer '+guard.key,'Content-Type':'application/json'},
                json={'model':'deepseek-flash','temperature':0.0,'thinking':{'type':'disabled'},'max_tokens':2048,'messages':messages},timeout=30,allow_redirects=False)
            return reply.json()['choices'][0]['message']['content']
    maps=[]
    for c in chunks:
        body=(registration['map_instruction']+'\n[QUESTION]\n'+work['question']+'\n[STRUCTURE INDEX]\n'+json.dumps(index,ensure_ascii=False)+
              f"\n[CHUNK {c['chunk_id']}; source {c['source_id']}; Unicode [{c['start']},{c['end']})]\n"+text[c['start']:c['end']])
        output=call([{'role':'system','content':registration['system_prompt']},{'role':'user','content':body}])
        maps.append({'chunk_id':c['chunk_id'],'map_call_id':guard.actual_attempts,'output':output})
    body=registration['reduce_instruction']+'\n[QUESTION]\n'+work['question']+'\n[MAP OUTPUTS]\n'+json.dumps(maps,ensure_ascii=False)
    answer=call([{'role':'system','content':registration['system_prompt']},{'role':'user','content':body}])
    intervals=[{k:c[k] for k in ('source_id','start','end')} for c in chunks]
    return {'answer':answer,'maps':maps,'chunks':chunks,'local_resolution_seconds':work.get('local_resolution_seconds') if arm=='A' else None,
            'selected_scope':work['resolution'] if arm=='A' else {'status':'UNASSESSABLE','reason':'deliberate full-source scan; map relevance needs independent adjudication'},
            'visited_source_intervals':intervals,'actual_model_input_intervals':intervals,
            'body_source_intervals':intervals,'structure_metadata_input':index,
            'actual_model_input_intervals_scope':'body_only; structure metadata recorded separately',
            'reduce_input':'map summaries only; two-hop support requires independent audit'}


def run_worker(profile,unit_id,unit_deadline=None,global_attempts_remaining=177):
    started=time.time();profile=Path(profile).resolve();reg=verify_registration(profile)
    unit=next(u for u in reg['schedule'] if u['unit_id']==unit_id)
    output=contained(profile,profile/'out/units'/unit_id);output.mkdir(parents=True,exist_ok=False)
    result={**unit,'status':'PROFILE_STOP','answer':None,'started_epoch':started}
    guard=None
    try:
        clear_unit_cache(profile,reg)
        from research.development_isolation import activate
        activate(reg['runtime'])
        guard=unit_guard_class()(output/'calls',os.environ.get('LANGEXTRACT_API_KEY',''),unit['arm'],unit['planned_max_attempts'],deadline=unit_deadline or started+120,global_attempts_remaining=global_attempts_remaining)
        work=next(w for w in reg['work'] if w['question_id']==unit['question_id'])
        with guard.install():
            if unit['arm']=='P0':
                import asyncio
                from research.development_isolation import query_source
                native=asyncio.run(query_source(reg['runtime'],unit['source_id'],work['question'],unit_id,guard))
                result.update(answer=native['response']['answer'],response=native['response'],trace=native['trace'],
                              selected_scope={'status':'UNASSESSABLE','reason':'implicit KG retrieval has no complete attribute/edge spans'},
                              visited_source_intervals=None,actual_model_input_intervals=None)
            else:
                text=(Path(reg['runtime'])/reg['sources'][unit['source_id']]['file']).read_bytes().decode('utf-8')
                result.update(map_reduce(unit,work,reg,guard,text))
        if guard.closed:result.update(status=guard.state.get('stop_kind','PROFILE_STOP'),answer=None)
        else:result['status']='COMPLETED'
    except Exception as exc:
        result.update(status=guard.state.get('stop_kind','PROFILE_STOP') if guard else 'PROFILE_STOP',answer=None,error_type=type(exc).__name__)
    finally:
        result['elapsed_seconds']=time.time()-started
        if time.time()>(unit_deadline or started+120):result.update(status='PROFILE_STOP',answer=None,stop_reason='本地单元超时，费用是否结束无法保证')
        try:verify_registration(profile);clear_unit_cache(profile,reg)
        except Exception:result.update(status='PROFILE_STOP',answer=None,stop_reason='执行资产验证失败')
        if guard:
            result['actual_attempts']=guard.actual_attempts
            result['usage']={'prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens',0) for r in guard.state['records']),
                             'completion_tokens':sum(r.get('usage',{}).get('completion_tokens',0) for r in guard.state['records']),
                             'unknown_cost_requests':sum(r.get('cost_status')=='UNKNOWN' for r in guard.state['records'])}
        dump(output/'result.json',result)
    return result


def supervise(profile,env_file):
    profile=Path(profile).resolve();reg=verify_registration(profile)
    status_path=profile/'out/profile-status.json'
    if status_path.exists() or (profile/'out/units').exists():raise ValueError('不自动续跑或重放已启动profile')
    from dotenv import dotenv_values
    key=dotenv_values(env_file).get('LANGEXTRACT_API_KEY')
    if not key:raise ValueError('运行缺少环境文件密钥')
    started=time.time();rows=[];stopped=False;attempts=0
    for unit in reg['schedule']:
        if stopped or time.time()-started>=5400:
            row={**unit,'status':'NOT_RUN','answer':None,'stop_reason':'先前单元停组或全局墙钟耗尽'}
            rows.append(row);dump(profile/'out/units'/unit['unit_id']/'result.json',row);continue
        remaining=5400-(time.time()-started)
        global_remaining=177-attempts
        if unit['planned_max_attempts']>global_remaining:
            stopped=True;row={**unit,'status':'NOT_RUN','answer':None,'stop_reason':'发前全组剩余额度不足登记路径'}
            rows.append(row);dump(profile/'out/units'/unit['unit_id']/'result.json',row);continue
        deadline=time.time()+min(120,remaining)
        command=[sys.executable,'-B','-X','utf8',str(Path(reg['runtime'])/'backend/research/common_three_arm.py'),'worker','--profile-root',str(profile),'--unit-id',unit['unit_id'],
                 '--unit-deadline',str(deadline),'--global-attempts-remaining',str(global_remaining)]
        env=child_environment(reg['runtime'],key)
        try:
            completed=subprocess.run(command,env=env,cwd=reg['runtime'],capture_output=True,text=True,encoding='utf-8',timeout=min(120,remaining))
            unit_path=profile/'out/units'/unit['unit_id'];result_path=unit_path/'result.json'
            # Native diagnostic output can contain source excerpts; never persist
            # raw exceptions/headers or a key echoed by an unexpected dependency.
            dump(profile/'out/process'/f"{unit['unit_id']}.json",{'exit_code':completed.returncode,'stdout_sha256':hashlib.sha256(completed.stdout.encode()).hexdigest(),
                'stderr_sha256':hashlib.sha256(completed.stderr.encode()).hexdigest(),'raw_output_omitted':True})
            row=load(result_path) if result_path.exists() else {**unit,'status':'PROFILE_STOP','answer':None,'stop_reason':'子进程未形成完整收据'}
            if completed.returncode:row.update(status='PROFILE_STOP',answer=None)
        except subprocess.TimeoutExpired:
            row={**unit,'status':'PROFILE_STOP','answer':None,'stop_reason':'单元进程超时，远端费用未知'}
            ledger=profile/'out/units'/unit['unit_id']/'calls/ledger.json'
            if ledger.exists():row['partial_ledger_sha256']=sha(ledger)
        ledger=profile/'out/units'/unit['unit_id']/'calls/ledger.json'
        if ledger.exists():
            try:
                state=load(ledger);row['actual_attempts']=state['actual_attempts']
                row['usage']={'prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens',0) for r in state['records']),
                              'completion_tokens':sum(r.get('usage',{}).get('completion_tokens',0) for r in state['records']),
                              'unknown_cost_requests':sum(r.get('cost_status')=='UNKNOWN' for r in state['records'])}
                if row['usage']['unknown_cost_requests'] or any(r['status']=='SENT_PENDING' for r in state['records']):row.update(status='PROFILE_STOP',answer=None)
            except (ValueError,KeyError,TypeError):row.update(status='PROFILE_STOP',answer=None,stop_reason='预算账本损坏')
        attempts+=row.get('actual_attempts',0)
        if attempts>177:row.update(status='PROFILE_STOP',answer=None,stop_reason='全组路径请求上限超额')
        rows.append(row);stopped=row['status']=='PROFILE_STOP'
        dump(profile/'out/units'/unit['unit_id']/'result.json',row)
        dump(status_path,{'status':'RUNNING' if not stopped else 'STOPPED','units':rows,'actual_attempts':attempts,'elapsed_seconds':time.time()-started})
    result={'status':'STOPPED' if stopped else ('GLOBAL_TIME_CAP' if any(r['status']=='NOT_RUN' for r in rows) else 'FINISHED'),
            'units':rows,'actual_attempts':attempts,'elapsed_seconds':time.time()-started,'registered_units':54,'gold_loaded':False}
    dump(status_path,result);verify_registration(profile);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run','worker'));parser.add_argument('--profile-root',required=True)
    parser.add_argument('--frozen-runtime');parser.add_argument('--inputs');parser.add_argument('--env-file');parser.add_argument('--unit-id')
    parser.add_argument('--unit-deadline',type=float);parser.add_argument('--global-attempts-remaining',type=int,default=177)
    args=parser.parse_args()
    try:
        if args.mode=='prepare':result=prepare(args.frozen_runtime,args.inputs,args.profile_root);print(json.dumps({'status':result['status'],'units':len(result['schedule']),'path_attempts':result['global_path_attempts']}))
        elif args.mode=='worker':result=run_worker(args.profile_root,args.unit_id,args.unit_deadline,args.global_attempts_remaining);print(json.dumps({'unit_id':args.unit_id,'status':result['status']}))
        else:result=supervise(args.profile_root,args.env_file);print(json.dumps({'status':result['status'],'units':len(result['units'])}))
    except Exception as exc:
        print(json.dumps({'status':'FAILED','error_type':type(exc).__name__}));raise SystemExit(1) from None


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));main()
