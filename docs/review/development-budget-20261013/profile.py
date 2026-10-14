"""Bounded public-development resource measurement; never a native P0 runner."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / 'docs/review/public-development-20261012/pilot/validated'
MAX_CALLS, MAX_OUTPUT, MAX_BYTES, MAX_SECONDS = 29, 2048, 600000, 900
CODE = ['backend/generator.py', 'backend/prompt_builder.py', 'backend/retrieval.py',
        'backend/routes/rag_query.py', 'backend/routes/query.py', 'backend/server.py',
        'backend/config.py', 'backend/models.py', 'backend/research/scope_v2.py']

def packed(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

def sha(b):
    return hashlib.sha256(b).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def snapshot():
    return {p: sha((ROOT / p).read_bytes()) for p in CODE}

def prompt_functions():
    # Compile only literal templates and pure message formatting, not imports,
    # retrieval, provider clients or production module initialization.
    tree = ast.parse((ROOT / 'backend/prompt_builder.py').read_text(encoding='utf-8'))
    names = {'SYSTEM_PROMPT', 'CONTEXT_TEMPLATE', 'CHARS_PER_TOKEN'}
    nodes = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets):
            nodes.append(n)
        elif isinstance(n, ast.FunctionDef) and n.name in {'_is_inventory_query', 'build_prompt'}:
            nodes.append(n)
    space = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<actual-production-message-formatting>', 'exec'), space)
    return space

MAP_INSTRUCTION = '''You are performing one map stage of a complete-document scan.
Check only the supplied excerpt against the exact requested scope. Extract all
supported relevant items, values, units, conditions, examples and caveats without
compressing distinct attributes. Preserve citations to this chunk. Return NONE
when no relevant evidence occurs. A partial excerpt cannot prove absence or
exhaustiveness. The structure index is navigation metadata, not factual evidence.
Do not answer from memory. Answer in the question's language.'''
REDUCE_INSTRUCTION = '''Merge the following map outputs for the question. Preserve
all distinct supported items and required attributes, conditions and caveats;
deduplicate only semantically identical entries. Retain original chunk citations.
Do not invent missing information or claim semantic exhaustiveness merely because
all chunks were scanned. Map summaries may have omissions. Answer in Chinese.'''

def prepare():
    sys.path.insert(0, str(ROOT / 'backend'))
    from research.scope_v2 import Source, resolve_scope
    sources = read(DATA / 'sources.json')
    questions = read(DATA / 'questions.input.json')
    assert len(questions) == 6 and all(set(q) == {'question_id', 'source_id', 'question', 'range_condition'} for q in questions)
    texts, indexes, chunks = {}, {}, {}
    inputs = {'questions.input.json': sha((DATA / 'questions.input.json').read_bytes()),
              'sources.json': sha((DATA / 'sources.json').read_bytes())}
    for s in sources:
        raw = (DATA / s['canonical_file']).read_bytes()
        assert sha(raw) == s['canonical_sha256']
        inputs[s['canonical_file']] = sha(raw)
        t = raw.decode('utf-8')
        texts[s['source_id']] = t
        if s['source_id'] == 'LCNC-HOME':
            blocks = read(DATA / s['section_or_page_map'])
            idx = [{'heading': b['text'], 'start': b['start'], 'end': b['end']}
                   for b in blocks if re.fullmatch('h[1-6]', b['tag'])]
        else:
            idx = []
            offset = 0
            for line in t.splitlines(keepends=True):
                if re.match(r'^\s*\d+(?:\.\d+)*[. ]+\s*[A-Za-z]', line):
                    idx.append({'candidate_heading': line.strip(), 'start': offset,
                                'status': 'TEXT_PATTERN_NOT_VERIFIED_HEADING'})
                offset += len(line)
        inputs[s['section_or_page_map']] = sha((DATA / s['section_or_page_map']).read_bytes())
        indexes[s['source_id']] = idx
        chunks[s['source_id']] = [{'id': f"{s['source_id']}-c{i//8000:03}", 'start': i,
                                    'end': min(i+8000, len(t)), 'text': t[i:i+8000]}
                                   for i in range(0, len(t), 8000)]
        assert ''.join(c['text'] for c in chunks[s['source_id']]) == t
    f = prompt_functions()
    units, auto = [], []
    for q in questions:
        start = time.monotonic()
        resolution = resolve_scope(q['question'], [Source(q['source_id'], texts[q['source_id']])])
        auto.append({'question_id': q['question_id'], **asdict(resolution),
                     'local_seconds': time.monotonic()-start, 'model_calls': 0,
                     'answer_budget_measured': False})
    for s in sources:
        q = next(q for q in questions if q['source_id'] == s['source_id'])
        c = chunks[s['source_id']][0]
        context = f"[{c['id']}]\n{c['text']}"
        f['_build_budgeted_context_sections'] = lambda **kw: context
        messages, metadata = f['build_prompt'](None, q['question'], max_context_tokens=4000, return_metadata=True)
        units.append({'call_id': f"diag-{s['source_id']}", 'arm': 'P0_PROMPT_ONLY_DIAGNOSTIC',
                      'question_id': q['question_id'], 'messages': messages,
                      'production_character_proxy_metadata': metadata,
                      'coverage': [{'source_id': s['source_id'], 'start': c['start'], 'end': c['end']}]})
    for q in questions:
        for c in chunks[q['source_id']]:
            content = (f"{MAP_INSTRUCTION}\n[QUESTION]\n{q['question']}\n"
                       f"[STRUCTURE INDEX]\n{json.dumps(indexes[q['source_id']], ensure_ascii=False)}\n"
                       f"[CHUNK {c['id']}; source {q['source_id']}; Unicode [{c['start']},{c['end']})]\n{c['text']}")
            units.append({'call_id': f"{q['question_id']}-map-{c['id']}", 'arm': 'S_SCAN_ALL',
                          'question_id': q['question_id'], 'stage': 'map',
                          'messages': [{'role': 'system', 'content': f['SYSTEM_PROMPT']}, {'role': 'user', 'content': content}],
                          'coverage': [{'source_id': q['source_id'], 'start': c['start'], 'end': c['end']}], 'chunk_id': c['id']})
        units.append({'call_id': f"{q['question_id']}-reduce", 'arm': 'S_SCAN_ALL',
                      'question_id': q['question_id'], 'stage': 'reduce',
                      'dynamic_messages': True, 'question': q['question'], 'system': f['SYSTEM_PROMPT']})
    assert len(units) == MAX_CALLS
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PREPARED_NOT_EXECUTED',
                'model_requested': 'deepseek-chat', 'temperature': 0.0,
                'max_calls': MAX_CALLS, 'max_completion_tokens_per_call': MAX_OUTPUT,
                'max_declared_completion_tokens': MAX_CALLS*MAX_OUTPUT,
                'messages_utf8_budget': MAX_BYTES, 'messages_serialization': 'UTF8 json ensure_ascii=False separators=comma_colon',
                'global_local_seconds': MAX_SECONDS, 'worker_local_seconds': 45,
                'retries': 0, 'inputs_sha256': inputs, 'code_sha256': snapshot(),
                'script_sha256': sha(Path(__file__).read_bytes()), 'auto_resolution': auto,
                'P0_NATIVE': {'status': 'CORPUS_UNAVAILABLE', 'answer_budget_measured': False},
                'source_counts': {k: {'unicode_characters': len(v), 'utf8_bytes': len(v.encode()), 'chunks': len(chunks[k])} for k,v in texts.items()},
                'units': units, 'map_instruction': MAP_INSTRUCTION, 'reduce_instruction': REDUCE_INSTRUCTION,
                'gold_loaded': False, 'scientific_stage': 'M2_OPEN'}
    save(HERE / 'manifest.json', manifest)
    print(json.dumps({'status': manifest['status'], 'calls': len(units), 'auto': [r['status'] for r in auto],
                      'sources': manifest['source_counts']}, ensure_ascii=False), flush=True)

def worker(request_path, response_path):
    import requests
    from dotenv import dotenv_values
    from urllib.parse import urlsplit
    payload = read(request_path)
    values = dotenv_values(ROOT / 'backend/.env')
    key = values.get('LANGEXTRACT_API_KEY')
    url = values.get('LANGEXTRACT_BASE_URL', '').rstrip('/')
    parsed = urlsplit(url)
    if (url != 'https://api.deepseek.com' or parsed.username or parsed.password or
        not key or values.get('LANGEXTRACT_MODEL_ID') != payload['model']):
        save(response_path, {'status': 'CONFIG_MISMATCH', 'usage_known': False, 'send_status': 'NOT_ATTEMPTED'})
        return
    start = time.monotonic()
    try:
        # requests has no automatic retry by default; redirects explicitly off.
        response = requests.post(url + '/chat/completions', json=payload,
                    headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'},
                    timeout=(10, 30), allow_redirects=False)
        if response.status_code != 200:
            result = {'status': 'HTTP_ERROR', 'http_status': response.status_code, 'usage_known': False}
        elif key in response.text:
            result = {'status': 'SECRET_RESPONSE_REJECTED', 'usage_known': False}
        else:
            data = response.json()
            usage = data.get('usage', {})
            valid = all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('prompt_tokens','completion_tokens','total_tokens'))
            valid = valid and usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens']
            choice = data.get('choices', [{}])[0]
            content = choice.get('message', {}).get('content')
            status = 'SUCCESS' if valid and isinstance(content, str) and content.strip() and choice.get('finish_reason') == 'stop' else 'INVALID_OR_TRUNCATED_RESPONSE'
            result = {'status': status, 'http_status': 200, 'usage_known': valid,
                      'provider_response': data}
        result['send_status'] = 'HTTP_RESPONSE_RECEIVED'
    except Exception as exc:
        result = {'status': 'TRANSPORT_OR_PARSE_ERROR', 'error_class': type(exc).__name__, 'usage_known': False,
                  'send_status': 'REQUEST_ATTEMPTED_DELIVERY_UNKNOWN'}
    result['worker_elapsed_seconds'] = time.monotonic()-start
    save(response_path, result)

def execute():
    m = read(HERE / 'manifest.json')
    assert snapshot() == m['code_sha256'], 'CODE_DRIFT'
    assert sha(Path(__file__).read_bytes()) == m['script_sha256'], 'SCRIPT_DRIFT'
    assert all(sha((DATA / p).read_bytes()) == h for p,h in m['inputs_sha256'].items()), 'INPUT_DRIFT'
    run = HERE / 'run-01'
    assert not run.exists(), 'NO_OVERWRITE_OR_RESUME'
    run.mkdir()
    calls, maps, used_bytes = [], {}, 0
    begin = time.monotonic()
    for i, unit in enumerate(m['units']):
        messages = unit.get('messages')
        if unit.get('dynamic_messages'):
            outputs = maps.get(unit['question_id'], [])
            messages = [{'role':'system', 'content': unit['system']},
                        {'role':'user', 'content': REDUCE_INSTRUCTION+'\n[QUESTION]\n'+unit['question']+'\n[MAP OUTPUTS]\n'+json.dumps(outputs,ensure_ascii=False)}]
        size = len(packed(messages))
        remaining = MAX_SECONDS-(time.monotonic()-begin)
        if i >= MAX_CALLS or used_bytes+size > MAX_BYTES or remaining <= 0:
            calls.append({'call_id': unit['call_id'], 'status':'RESOURCE_CAP_NOT_SENT', 'usage_known': False, 'send_status': 'NOT_ATTEMPTED'})
            save(run / 'ledger.json', calls)
            break
        payload = {'model':m['model_requested'], 'messages':messages,'temperature':0.0,'max_tokens':MAX_OUTPUT}
        request_path, response_path = run / f'{i:02}-{unit["call_id"]}.request.json', run / f'{i:02}-{unit["call_id"]}.response.json'
        save(request_path, payload)
        start = time.monotonic()
        remaining = MAX_SECONDS-(start-begin)
        if remaining <= 0:
            calls.append({'call_id': unit['call_id'], 'status':'RESOURCE_CAP_NOT_SENT', 'usage_known':False, 'send_status':'NOT_ATTEMPTED'})
            save(run / 'ledger.json', calls)
            break
        used_bytes += size
        try:
            subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(__file__)), '--worker', str(request_path), str(response_path)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=min(45,remaining))
            result = read(response_path)
        except subprocess.TimeoutExpired:
            result = {'status':'LOCAL_DEADLINE_REMOTE_COST_UNKNOWN','usage_known':False, 'send_status':'UNKNOWN'}
            save(response_path,result)
        except Exception as exc:
            result = {'status':'WORKER_ERROR','error_class':type(exc).__name__,'usage_known':False, 'send_status':'UNKNOWN'}
            save(response_path,result)
        record = {k:v for k,v in unit.items() if k not in {'messages','system','question'}}
        record.update({'status':result['status'], 'send_status':result['send_status'], 'attempted_worker':True,
                       'usage_known':result['usage_known'],'messages_utf8_bytes':size,
                       'messages_sha256':sha(packed(messages)), 'request_path':request_path.name,
                       'request_sha256':sha(request_path.read_bytes()), 'response_path':response_path.name,
                       'response_sha256':sha(response_path.read_bytes()), 'elapsed_seconds':time.monotonic()-start})
        data = result.get('provider_response', {})
        if result['usage_known']:
            record['usage'] = data['usage']
        record['provider_model'] = data.get('model')
        record['provider_id'] = data.get('id')
        record['system_fingerprint'] = data.get('system_fingerprint')
        calls.append(record)
        save(run / 'ledger.json', calls)
        print(json.dumps({'progress':f'{i+1}/{MAX_CALLS}', 'call_id':unit['call_id'], 'status':result['status'], 'usage':record.get('usage')},ensure_ascii=False),flush=True)
        if result['status'] != 'SUCCESS':
            break
        if unit.get('stage') == 'map':
            maps.setdefault(unit['question_id'], []).append({'chunk_id':unit['chunk_id'], 'map_call_id':unit['call_id'],
                                  'output':data['choices'][0]['message']['content']})
    known = [c['usage'] for c in calls if c.get('usage')]
    summary = {'status':'PROFILE_COMPLETE' if len(calls)==MAX_CALLS and all(c['status']=='SUCCESS' for c in calls) else 'PROFILE_STOPPED',
               'attempted_workers':sum(c.get('attempted_worker',False) for c in calls),
               'known_usage_subtotal':{k:sum(u[k] for u in known) for k in ('prompt_tokens','completion_tokens','total_tokens')},
               'total_cost_complete':all(c['usage_known'] or c['send_status']=='NOT_ATTEMPTED' for c in calls),
               'messages_utf8_bytes':used_bytes, 'elapsed_seconds':time.monotonic()-begin,
               'code_after_sha256':snapshot(), 'code_unchanged':snapshot()==m['code_sha256'],
               'three_baseline_budget_frozen':False, 'semantic_scoring':'NOT_EXECUTED', 'scientific_stage':'M2_OPEN'}
    save(run / 'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--prepare',action='store_true')
    p.add_argument('--execute-authorized-public-profile',action='store_true')
    p.add_argument('--worker',nargs=2)
    args = p.parse_args()
    if args.worker:
        worker(*map(Path,args.worker))
    elif args.prepare:
        prepare()
    elif args.execute_authorized_public_profile:
        execute()
    else:
        p.error('explicit mode required')
