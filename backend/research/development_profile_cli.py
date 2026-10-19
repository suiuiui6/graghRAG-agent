"""Public-development input preparation and A budget consumer (no Gold loading).

Prepare can run without a key; run-a uses only a caller-injected environment key
and the shared fail-closed transport ledger. Production services are never started.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def dump(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare_inputs(data_dir, xml, artifacts, previous_manifest, *, progress=None):
    from research.scope_v2 import Source, assemble_scope
    from research.development_structure import build_html_structure, build_pdf_structure
    from research.development_scope import resolve_development_scope
    data, artifacts = Path(data_dir).resolve(), Path(artifacts).resolve()
    records, questions = load(data/'sources.json'), load(data/'questions.input.json')
    assert len(questions) == 6
    assert all(set(q) == {'question_id','source_id','question','range_condition'} for q in questions)
    sources, structures, summaries, hashes = {}, {}, {}, {}
    for r in records:
        canonical, raw = (data/r['canonical_file']).resolve(), (data/r['raw_file']).resolve()
        assert raw.is_relative_to(data.parent) and canonical.is_relative_to(data)
        assert sha(canonical) == r['canonical_sha256'] and sha(raw) == r['source_sha256']
        text = canonical.read_bytes().decode('utf-8')
        source = Source(r['source_id'], text)
        mapping = load(data/r['section_or_page_map'])
        entries = mapping.get('blocks' if raw.suffix=='.html' else 'pages') if isinstance(mapping,dict) else mapping
        start = time.monotonic()
        index = (build_html_structure(source,raw.read_bytes(),entries) if raw.suffix=='.html'
                 else build_pdf_structure(source,entries,Path(xml).read_bytes()))
        sources[source.key], structures[source.key] = source,index
        summaries[source.key] = {'unicode_characters':len(text),'structure_seconds':time.monotonic()-start,
                                 'structure':asdict(index)}
        for p in (canonical,raw,data/r['section_or_page_map']): hashes[str(p)] = sha(p)
    work = []
    for q in questions:
        source, index = sources[q['source_id']], structures[q['source_id']]
        start = time.monotonic()
        resolution = resolve_development_scope(q['question'],[source],[index])
        assembly = assemble_scope(resolution,[source],max_bytes=120000)
        spans = []
        # Use native assembly's merged, actually-read source mappings; all model
        # excerpts are exact source slices, never synthetic inter-span separators.
        for mapping in assembly.mappings:
            for offset in range(mapping['start'],mapping['end'],8000):
                end = min(offset+8000,mapping['end'])
                spans.append({'source_id':source.key,'start':offset,'end':end,
                              'chunk_id':f'{source.key}-A-{offset}-{end}'})
        work.append({**q,'resolution':asdict(resolution),'assembly':{
            'status':assembly.status,'utf8_bytes':assembly.utf8_bytes,'characters':assembly.characters,
            'mappings':list(assembly.mappings)},'local_resolution_seconds':time.monotonic()-start,
            'chunks':spans,'planned_calls':len(spans)+1 if assembly.status=='COMPLETE_SCOPE' and spans else 0})
    old=load(previous_manifest)
    receipt={'status':'PREPARED_NOT_EXECUTED','data_dir':str(data),'xml':str(Path(xml).resolve()),
             'input_hashes':hashes,'questions_sha256':sha(data/'questions.input.json'),
             'source_manifest_sha256':sha(data/'sources.json'),'xml_sha256':sha(xml),
             'previous_manifest_sha256':sha(previous_manifest),'previous_manifest':str(Path(previous_manifest).resolve()),
             'system_prompt':old['units'][0]['messages'][0]['content'],
             'map_instruction':old['map_instruction'],'reduce_instruction':old['reduce_instruction'],
             'sources':summaries,'work':work,'A_planned_calls':sum(w['planned_calls'] for w in work),
             'gold_loaded':False,'semantic_scoring':'NOT_EXECUTED','model_requested':'deepseek-flash',
             'thinking':'disabled','scientific_stage':'M2_OPEN'}
    assert receipt['A_planned_calls'] <= 22
    dump(artifacts/'inputs.json',receipt)
    if progress is not None:
        progress({'status':receipt['status'],'A_planned_calls':receipt['A_planned_calls'],
                      'resolution_statuses':[w['resolution']['status'] for w in work]})

def run_a(run_root, artifacts, ledger, *, progress=None):
    from research.development_isolation import activate, verify_snapshot
    activate(run_root)
    from research.development_budget import BudgetGuard
    import requests
    artifacts=Path(artifacts).resolve(); prepared=load(artifacts/'inputs.json')
    assert all(sha(p)==h for p,h in prepared['input_hashes'].items())
    assert sha(Path(prepared['data_dir'])/'questions.input.json')==prepared['questions_sha256']
    assert sha(prepared['xml'])==prepared['xml_sha256']
    guard=BudgetGuard(ledger,os.environ.get('LANGEXTRACT_API_KEY',''))
    texts={r['source_id']:(Path(prepared['data_dir'])/r['canonical_file']).read_bytes().decode('utf-8')
           for r in load(Path(prepared['data_dir'])/'sources.json')}
    result=[]
    with guard.install():
        def call(messages,qid):
            with guard.phase('a',qid):
                response=requests.post('https://api.deepseek.com/chat/completions',
                    headers={'Authorization':'Bearer '+guard.key,'Content-Type':'application/json'},
                    json={'model':'deepseek-flash','temperature':0.0,'max_tokens':2048,
                          'thinking':{'type':'disabled'},'messages':messages},timeout=30,allow_redirects=False)
                payload=response.json()
                return payload['choices'][0]['message']['content']
        for w in prepared['work']:
            qid=w['question_id']; started=time.monotonic(); maps=[]
            if not w['planned_calls']:
                result.append({'question_id':qid,'status':w['assembly']['status'],'calls':0})
                continue
            index=[{'heading':n['title'],'start':n['start'],'end':n['end']}
                   for n in prepared['sources'][w['source_id']]['structure']['nodes'] if n['kind']=='heading']
            for c in w['chunks']:
                body=(prepared['map_instruction']+'\n[QUESTION]\n'+w['question']+
                      '\n[STRUCTURE INDEX]\n'+json.dumps(index,ensure_ascii=False)+
                      f"\n[CHUNK {c['chunk_id']}; source {c['source_id']}; Unicode [{c['start']},{c['end']})]\n"+
                      texts[c['source_id']][c['start']:c['end']])
                output=call([{'role':'system','content':prepared['system_prompt']},{'role':'user','content':body}],qid)
                maps.append({'chunk_id':c['chunk_id'],'map_call_id':f"{qid}-map-{c['chunk_id']}",'output':output})
            body=(prepared['reduce_instruction']+'\n[QUESTION]\n'+w['question']+
                  '\n[MAP OUTPUTS]\n'+json.dumps(maps,ensure_ascii=False))
            answer=call([{'role':'system','content':prepared['system_prompt']},{'role':'user','content':body}],qid)
            row={'arm':'A_AUTO_READ','question_id':qid,'status':'COMPLETED','resolution':w['resolution'],
                 'chunks':w['chunks'],'maps':maps,'answer':answer,'elapsed_seconds':time.monotonic()-started}
            dump(artifacts/f'{qid}.a.json',row); result.append(row)
            if progress is not None:
                progress({'question_id':qid,'status':'COMPLETED','actual_attempts':guard.actual_attempts})
    verify_snapshot(run_root)
    dump(artifacts/'A-result.json',{'work':result,'semantic_scoring':'NOT_EXECUTED','scientific_stage':'M2_OPEN'})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare-inputs','run-a'))
    p.add_argument('--data-dir');p.add_argument('--xml');p.add_argument('--previous-manifest')
    p.add_argument('--artifacts',required=True);p.add_argument('--run-root');p.add_argument('--ledger')
    a=p.parse_args()
    if a.mode=='prepare-inputs': prepare_inputs(a.data_dir,a.xml,a.artifacts,a.previous_manifest, progress=lambda event: print(json.dumps(event,ensure_ascii=False)))
    else: run_a(a.run_root,a.artifacts,a.ledger, progress=lambda event: print(json.dumps(event),flush=True))

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    main()
