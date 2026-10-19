"""Post-generation anonymous content packets; never imported by generators."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def validate_judgments(packet_path: Path, judgments_path: Path):
    """Structural coverage only; never infer semantic correctness from text matches."""
    packet, judged = load(packet_path), load(judgments_path)
    gold = {q['question_id']:q for q in packet['questions']}
    answers = {a['answer_id']:a for a in packet['answers']}
    rows = judged['answers']
    assert len(rows)==len(answers) and {r['answer_id'] for r in rows}==set(answers)
    for row in rows:
        answer = answers[row['answer_id']]
        assert row['question_id']==answer['question_id']
        expected = gold[row['question_id']]
        assert len(row['items'])==len(expected['items'])
        by_item = {i['item_id']:i for i in row['items']}
        assert set(by_item)=={i['item_id'] for i in expected['items']}
        for item in expected['items']:
            actual = by_item[item['item_id']]
            assert actual['present'] is None or type(actual['present']) is bool
            atoms = actual['atoms']
            assert len(atoms)==len(item['atoms'])
            assert {a['atom_id'] for a in atoms}=={a['atom_id'] for a in item['atoms']}
            for atom in atoms:
                assert atom['correct'] is None or type(atom['correct']) is bool
                assert isinstance(atom['reason'],str)
                quote = atom['quote']
                assert isinstance(quote,str) and (not quote or quote in answer['answer'])
                if atom['correct'] is True:
                    assert quote, 'True atom requires actual answer quote'
        assert {q['id'] for q in row['qualifiers']}=={q['id'] for q in expected['qualifiers']}
        assert isinstance(row['extra_items'],list) and isinstance(row['completeness_claims'],list)
    return {'status':'STRUCTURAL_VALIDATION_ONLY','answers':len(rows),
            'semantic_correctness':'REQUIRES_INDEPENDENT_REVIEW'}


def prepare_evidence(profile: Path, *, progress=None):
    """Reveal actual calls only after both independent content files are locked."""
    output=profile/'evaluation';lock=load(output/'content-lock.json')
    assert len(lock['reviewers'])==2
    for reviewer in lock['reviewers']:
        path=output/reviewer['file']
        assert sha(path)==reviewer['sha256']
        validate_judgments(output/'content-packet.json',path)
    mapping=load(output/'operator-only-mapping.json')
    content=load(output/'content-packet.json')
    answers={a['answer_id']:a for a in content['answers']}
    questions={q['question_id']:q for q in content['questions']}
    for qid,q in questions.items():
        requests={};units=[]
        for row in mapping:
            answer=answers[row['answer_id']]
            if answer['question_id']!=qid:continue
            path=profile/'out/units'/row['unit_id']
            result=load(path/'result.json');calls=[]
            ledger=path/'calls/ledger.json'
            for record in load(ledger)['records'] if ledger.exists() else []:
                if 'request_wire_utf8' not in record:continue
                request_hash=record['request_sha256']
                assert request_hash==hashlib.sha256(record['request_wire_utf8'].encode()).hexdigest()
                requests[request_hash]=record['request']['messages']
                response=record.get('response',{});choices=response.get('choices',[])
                calls.append({'call_id':record['id'],'request_sha256':request_hash,
                    'response_sha256':record.get('response_sha256'),'status':record['status'],
                    'output':choices[0]['message']['content'] if choices else None})
            units.append({'answer_id':row['answer_id'],'unit_id':row['unit_id'],'arm':row['arm'],
                'status':result['status'],'answer':answer['answer'],'calls':calls,
                'selected_scope':result.get('selected_scope'),
                'body_source_intervals':result.get('body_source_intervals'),
                'structure_metadata_input':result.get('structure_metadata_input'),
                'maps':result.get('maps'), 'chunks':result.get('chunks')})
        save(output/f'evidence-{qid}.json',{'question':q,'units':units,'actual_request_messages_by_sha256':requests,
             'mode':'REVEALED_INPUT_SUPPORT_AUDIT_AFTER_CONTENT_LOCK'})
    if progress is not None:
        progress({'status':'EVIDENCE_PACKS_PREPARED','questions':len(questions)})


def prepare(profile: Path, gold_path: Path, *, progress=None):
    registration = load(profile/'registration.json')
    status_path = profile/'out/profile-status.json'
    if not status_path.exists():
        raise ValueError('Generation has not terminated; cannot expose Gold')
    if load(status_path).get('status') not in {'FINISHED','STOPPED','GLOBAL_TIME_CAP'}:
        raise ValueError('Generation status is not terminal')
    # A complete result per scheduled unit is required, including explicit failures.
    schedule = registration['schedule']
    assert len(schedule) == 54
    rows = []
    for unit in schedule:
        uid = unit['unit_id']
        path = profile/'out/units'/uid/'result.json'
        if path.exists():
            result = load(path)
            assert result['unit_id'] == uid
            rows.append((unit, result, path))
        else:
            raise ValueError('Missing registered unit result: '+uid)
    if any(r['status'] in {'RUNNING','PENDING'} for _,r,_ in rows):
        raise ValueError('Generation still active')
    output = profile/'evaluation'
    if output.exists():
        raise ValueError('Refuse to overwrite existing assessment packet')
    gold = load(gold_path)
    compact = []
    for q in gold['questions']:
        items = []
        for n, item in enumerate(q['gold_items'], 1):
            items.append({'item_id':f'I{n:02d}', 'item':item['item'],
                'atoms':[{'atom_id':a['atom_id'], 'expected':a['expected'],
                    'source_quotes':list(dict.fromkeys(e['quote'] for e in a.get('evidence',[])))}
                    for a in item['scoring_atoms']]})
        compact.append({'question_id':q['question_id'],'question':q['question'],
            'items':items,'scoring_notes':q.get('scoring_notes',[]),
            'qualifiers':[{'id':f'Q{n:02d}','expected':x['claim']}
                for n,x in enumerate(q.get('required_answer_qualifiers',[]),1)]})
    assert sum(len(q['items']) for q in compact)==36
    assert sum(len(i['atoms']) for q in compact for i in q['items'])==81
    random.Random(20261015).shuffle(rows)
    answers, mapping = [], []
    for n,(unit,result,path) in enumerate(rows,1):
        aid=f'B{n:03d}'
        answers.append({'answer_id':aid,'question_id':unit['question_id'],
            'answer':result.get('answer') or '','run_status':result['status']})
        mapping.append({'answer_id':aid,'unit_id':unit['unit_id'],'arm':unit['arm'],
            'repeat':unit['repeat'],'result_path':str(path),'result_sha256':sha(path)})
    groups={}
    for answer in answers:
        identity=hashlib.sha256((answer['question_id']+'\0'+answer['answer']+'\0'+answer['run_status']).encode()).hexdigest()
        groups.setdefault(identity,[]).append(answer['answer_id'])
    save(output/'content-packet.json', {'review_mode':'AI_REVIEW_ONLY',
        'human_gold_verified':False, 'blindness_limit':'Styles/citations may reveal method; single operator knows mapping.',
        'questions':compact,'answers':answers,
        'exact_content_groups':list(groups.values())})
    save(output/'operator-only-mapping.json',mapping)
    save(output/'packet-freeze.json',{'registration_sha256':sha(profile/'registration.json'),
        'profile_status_sha256':sha(status_path),'gold_sha256':sha(gold_path),
        'content_packet_sha256':sha(output/'content-packet.json'),
        'mapping_sha256':sha(output/'operator-only-mapping.json'),
        'answer_count':len(answers),'unique_texts':len(set(a['answer'] for a in answers)),
        'scoring_atoms_per_repeat_arm':81, 'content_judgments':'NOT_EXECUTED'})
    if progress is not None:
        progress({'answers':len(answers),'unique_texts':len(set(a['answer'] for a in answers))})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--gold',type=Path,required=True)
    a=p.parse_args()
    prepare(a.profile.resolve(),a.gold.resolve(), progress=lambda event: print(json.dumps(event)))
