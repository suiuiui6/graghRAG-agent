"""Descriptive aggregation of locked independent judgments; no model scoring."""
import argparse
import hashlib
import json
from pathlib import Path

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def summarize(profile, *, progress=None):
    from research.common_evaluation_packets import validate_judgments
    out=profile/'evaluation'
    validate_judgments(out/'content-packet.json',out/'content-final.json')
    content=load(out/'content-final.json'); evidence=load(out/'evidence-final.json')
    packet=load(out/'content-packet.json')
    answers={a['answer_id']:a for a in packet['answers']}
    mapping={m['answer_id']:m for m in load(out/'operator-only-mapping.json')}
    e_by_id={e['answer_id']:e for e in evidence['answers']}
    assert len(evidence['answers'])==len(e_by_id)==len(answers)==54 and set(e_by_id)==set(answers)
    results=[]
    for row in content['answers']:
        aid=row['answer_id']; actual=answers[aid]; trace=e_by_id[aid]; info=mapping[aid]
        atoms=[a for i in row['items'] for a in i['atoms']]
        correct=sum(a['correct'] is True for a in atoms)
        present=sum(i['present'] is True for i in row['items'])
        tuples=sum(i['present'] is True and all(a['correct'] is True for a in i['atoms']) for i in row['items'])
        unknown_atoms=sum(a['correct'] is None for a in atoms)
        # The blind content records stay immutable. Extra facts that could not be
        # verified without source/input access are resolved in the separate audit.
        extras=[dict(x) for x in row['extra_items']];claims=trace['claims']
        metadata_claims=trace.get('metadata_claims',[])
        updates=trace.get('extra_adjudications',[])
        indices=[u['extra_index'] for u in updates]
        assert len(indices)==len(extras) and all(type(i) is int for i in indices)
        assert len(set(indices))==len(indices)
        assert {u['extra_index'] for u in updates}==set(range(len(extras)))
        for update in updates:
            extra=extras[update['extra_index']]
            extra['blind_content_reason']=extra.get('reason')
            extra['reason']=update['reason']
            extra['source_locators']=update.get('source_locators',[])
            for key in ('correct','in_scope'):
                assert update[key] is None or type(update[key]) is bool
                extra[key]=update[key]
        assert trace.get('claim_audit_complete') is True
        for claim in claims+metadata_claims:
            for key in ('content_correct','in_scope','input_supported','citation_entails'):
                assert claim[key] is None or type(claim[key]) is bool
        supported=sum(c['input_supported'] is True for c in claims)
        in_scope_supported=sum(c['input_supported'] is True and c['in_scope'] is True for c in claims)
        unknown_support=sum(c['input_supported'] is None for c in claims)
        cited=sum(c['citation_entails'] is True for c in claims)
        completeness=trace['completeness_claims']
        assert trace.get('completeness_audit_complete') is True
        promise_indices=[v['content_claim_index'] for v in completeness]
        assert len(promise_indices)==len(row['completeness_claims'])
        assert all(type(i) is int for i in promise_indices) and len(set(promise_indices))==len(promise_indices)
        assert set(promise_indices)==set(range(len(row['completeness_claims'])))
        for verdict in completeness:
            assert verdict['text']==row['completeness_claims'][verdict['content_claim_index']]['text']
            assert isinstance(verdict['status'],list) and verdict['status']
        required_complete=(present==len(row['items']) and correct==len(atoms) and
            all(q['correct'] is True for q in row['qualifiers']))
        content_complete=(required_complete and
            all(x['correct'] is True and x['in_scope'] is True for x in extras))
        strict=(actual['run_status']=='COMPLETED' and content_complete and bool(claims)
            and all(c['input_supported'] is True and c['in_scope'] is True and c['content_correct'] is True for c in claims+metadata_claims)
            and all(set(verdict['status'])=={'SUPPORTED_COMPLETENESS'} for verdict in completeness))
        assessable=actual['run_status']=='COMPLETED'
        predicted=row.get('predicted_item_count')
        assert predicted is None or (type(predicted) is int and predicted>=present)
        results.append({'answer_id':aid,**{k:info[k] for k in ('unit_id','arm','repeat')},
            'question_id':actual['question_id'],'run_status':actual['run_status'],
            'scope_selection':trace.get('scope_selection','UNASSESSABLE'),
            'gold_items':len(row['items']),'items_present':present if assessable else None,
            'item_recall':present/len(row['items']) if assessable else None,
            'predicted_item_count':predicted,'item_precision':present/predicted if assessable and predicted else None,
            'strict_tuples':tuples if assessable else None,'scoring_atoms':len(atoms),
            'atoms_correct':correct if assessable else None,'atoms_unknown':unknown_atoms if assessable else None,
            'atom_accuracy':correct/len(atoms) if assessable else None,
            'content_complete':content_complete if assessable else None,
            'required_content_complete':required_complete if assessable else None,
            'source_adjudicated_extra_items':extras,
            'fact_claims':len(claims) if assessable else None,'input_supported_claims':supported if assessable else None,
            'input_support_rate':supported/len(claims) if assessable and claims else None,
            'in_scope_supported_claims':in_scope_supported if assessable else None,
            'in_scope_support_rate':in_scope_supported/len(claims) if assessable and claims else None,
            'unknown_support_claims':unknown_support if assessable else None,
            'unknown_support_rate':unknown_support/len(claims) if assessable and claims else None,
            'metadata_claims':len(metadata_claims),
            'metadata_input_supported':sum(c['input_supported'] is True for c in metadata_claims),
            'metadata_content_false':sum(c['content_correct'] is False for c in metadata_claims),
            'metadata_input_unsupported':sum(c['input_supported'] is False for c in metadata_claims),
            'metadata_unknown':sum(any(c[k] is None for k in ('input_supported','in_scope','content_correct')) for c in metadata_claims),
            'citation_entails_claims':cited if assessable else None,
            'citation_entailment_rate':cited/len(claims) if assessable and claims else None,
            'completeness_claims':completeness,
            'strict_supported_complete':strict})
    groups=[]
    for arm in ('P0','A','S'):
        for qid in sorted({r['question_id'] for r in results}):
            units=[r for r in results if r['arm']==arm and r['question_id']==qid]
            assert len(units)==3
            groups.append({'arm':arm,'question_id':qid,'registered_units':3,
                'completed_units':sum(r['run_status']=='COMPLETED' for r in units),
                'item_recall_by_repeat':[r['item_recall'] for r in sorted(units,key=lambda r:r['repeat'])],
                'atom_accuracy_by_repeat':[r['atom_accuracy'] for r in sorted(units,key=lambda r:r['repeat'])],
                'input_support_by_repeat':[r['input_support_rate'] for r in sorted(units,key=lambda r:r['repeat'])],
                'strict_successes':sum(r['strict_supported_complete'] for r in units)})
    summary={'status':'DESCRIPTIVE_DEVELOPMENT_ONLY','units':results,'question_arm_groups':groups,
        'input_hashes':{name:sha(out/name) for name in ('content-packet.json','content-final.json','evidence-final.json','operator-only-mapping.json')},
        'independent_sources':2,'questions':6,'repeats_are_independent_documents':False,
        'human_gold_verified':False,'scientific_stage':'M2_OPEN','inferential_tests':[]}
    (out/'quality-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if progress is not None:
        progress({'status':summary['status'],'units':len(results),
        'strict_successes_by_arm':{a:sum(r['strict_supported_complete'] for r in results if r['arm']==a) for a in ('P0','A','S')}})
    return summary

if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True,type=Path)
    summarize(p.parse_args().profile.resolve(), progress=lambda event: print(json.dumps(event)))
