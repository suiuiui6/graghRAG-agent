"""Supervisor for the user-authorized PUBLIC-only budget profile.

Loads the existing key into child memory only. Captures upstream stdout/stderr in
memory and emits controlled status; raw exception logs are never persisted.
Requires an already prepared, reviewed source snapshot and public inputs.json.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',required=True);p.add_argument('--run-root',required=True)
    p.add_argument('--artifacts',required=True);p.add_argument('--python',required=True)
    args=p.parse_args()
    repo,root,out=map(lambda x:Path(x).resolve(),(args.repo_root,args.run_root,args.artifacts))
    assert root.is_relative_to(repo/'.tmp') and out.is_relative_to(repo/'docs/review')
    assert (root/'snapshot.json').exists() and not (out/'execution-status.json').exists()
    inputs=json.loads((out/'inputs.json').read_text(encoding='utf-8'))
    assert inputs['gold_loaded'] is False and inputs['model_requested']=='deepseek-flash'
    assert inputs['A_planned_calls']==14
    from dotenv import dotenv_values
    values=dotenv_values(repo/'backend/.env')
    key=values.get('LANGEXTRACT_API_KEY')
    assert key and values.get('LANGEXTRACT_MODEL_ID')=='deepseek-flash'
    assert values.get('LANGEXTRACT_BASE_URL','').rstrip('/')=='https://api.deepseek.com'
    # Do not inherit unrelated provider credentials or per-user application state.
    env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT','COMSPEC','NUMBER_OF_PROCESSORS',
            'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','SSL_CERT_DIR') if k in os.environ}
    env.update(LANGEXTRACT_API_KEY=key,LANGEXTRACT_MODEL_ID='deepseek-flash',
               LANGEXTRACT_BASE_URL='https://api.deepseek.com',LANGEXTRACT_TEMPERATURE='0.0',
               PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',HF_ENDPOINT='https://huggingface.co',
               HOME=str(root/'home'),USERPROFILE=str(root/'home'),APPDATA=str(root/'home/AppData/Roaming'),
               LOCALAPPDATA=str(root/'home/AppData/Local'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    common=['--run-root',str(root),'--ledger',str(out/'calls')]
    isolation=root/'backend/research/development_isolation.py'
    commands=[('index',600,[str(isolation),'index',*common,'--sources',str(Path(inputs['data_dir'])/'sources.json'),
                           '--pdf-xml',inputs['xml']])]
    for w in inputs['work']:
        commands.append((w['question_id']+'-p0',120,[str(isolation),'query',*common,'--document-id',w['source_id'],
                            '--question',w['question'],'--question-id',w['question_id']]))
    commands.append(('A-all',600,[str(root/'backend/research/development_profile_cli.py'),'run-a',
                    '--run-root',str(root),'--artifacts',str(out),'--ledger',str(out/'calls')]))
    start=time.monotonic();rows=[]
    for name,limit,command in commands:
        remaining=1800-(time.monotonic()-start)
        if remaining<=0:
            rows.append({'step':name,'status':'LOCAL_WINDOW_NOT_STARTED'});break
        before=time.monotonic()
        try:
            result=subprocess.run([args.python,'-B','-X','utf8',*command],env=env,cwd=root,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=min(limit,remaining),check=False)
            row={'step':name,'exit_code':result.returncode,'status':'COMPLETED' if result.returncode==0 else 'FAILED',
                 'upstream_logs_omitted':True,'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr)}
            # Controlled JSON status emitted by our CLI can be retained. Never
            # retain arbitrary upstream logs, even when a library prints them.
            safe=[]
            for line in result.stdout.decode('utf-8',errors='replace').splitlines():
                try: d=json.loads(line)
                except ValueError: continue
                if isinstance(d,dict) and set(d).issubset({'status','error_type','actual_attempts','question_id'}):
                    if key not in line: safe.append(d)
            row['safe_child_status']=safe
        except subprocess.TimeoutExpired:
            row={'step':name,'status':'LOCAL_DEADLINE_REMOTE_COST_UNKNOWN','exit_code':None}
        row['elapsed_seconds']=time.monotonic()-before;rows.append(row)
        save(out/'execution-status.json',{'steps':rows,'elapsed_seconds':time.monotonic()-start,
             'generation':'USER_AUTHORIZED_REMOTE','semantic_scoring':'NOT_EXECUTED','scientific_stage':'M2_OPEN'})
        print(json.dumps({'step':name,'status':row['status'],'seconds':round(row['elapsed_seconds'],3)}),flush=True)
        if row['status']!='COMPLETED':break
    save(out/'execution-status.json',{'steps':rows,'elapsed_seconds':time.monotonic()-start,
        'generation':'USER_AUTHORIZED_REMOTE','semantic_scoring':'NOT_EXECUTED','scientific_stage':'M2_OPEN',
        'all_steps_completed':len(rows)==len(commands) and all(r['status']=='COMPLETED' for r in rows)})

if __name__=='__main__':main()
