"""Development target-region visit diagnostics, distinct from scope selection."""
import argparse
import json
from pathlib import Path

REASONS={
 'DEV-L01':'section6 opening actual table through note; before first child heading',
 'DEV-L02':'entire numbered6.10 including both notes',
 'DEV-L03':'continuous numbered6.1 through6.3',
 'DEV-L04':'entire numbered6.11 including five code examples',
 'DEV-L05':'entire numbered6.14 including code and omission note',
 'DEV-N01':'entire numbered3 including3.1 as requested; target list region is smaller and not the permitted-context boundary'}

def bindings(value):
    result=[]
    if isinstance(value,dict):
        if 'canonical_char_half_open' in value:result.append(value['canonical_char_half_open'])
        for child in value.values():result.extend(bindings(child))
    elif isinstance(value,list):
        for child in value:result.extend(bindings(child))
    return result

def audit(profile,gold_path, *, progress=None):
    reg=json.loads((profile/'registration.json').read_text(encoding='utf-8'))
    assert json.loads((profile/'out/profile-status.json').read_text(encoding='utf-8'))['status']=='FINISHED'
    gold={q['question_id']:q for q in json.loads(gold_path.read_text(encoding='utf-8'))['questions']}
    rows=[]
    for work in reg['work']:
        q=gold[work['question_id']];t0,t1=q['scope']['canonical_char_half_open'];evidence=bindings(q)
        for arm in ('A','S','P0'):
            chunks=work['chunks'] if arm=='A' else reg['sources'][work['source_id']]['chunks'] if arm=='S' else None
            intervals=[]
            for c in chunks or []:
                if intervals and intervals[-1][1]==c['start']:intervals[-1][1]=c['end']
                else:intervals.append([c['start'],c['end']])
            length=sum(b-a for a,b in intervals)
            overlap=sum(max(0,min(b,t1)-max(a,t0)) for a,b in intervals)
            covered=sum(any(a<=s and e<=b for a,b in intervals) for s,e in evidence) if chunks else None
            rows.append({'question_id':work['question_id'],'arm':arm,
                'selected_scope_verdict':'CORRECT' if arm=='A' else 'UNASSESSABLE',
                'selection_reason':REASONS[work['question_id']] if arm=='A' else 'Implicit model/KG selection lacks precise complete source-span mapping; source visits are not selection',
                'body_visited_intervals':intervals if chunks else None,
                'target_region_access_precision':overlap/length if length else None,
                'target_region_access_recall':overlap/(t1-t0) if length else None,
                'gold_bound_regions':len(evidence),'gold_bound_regions_fully_visited':covered,
                'semantic_scope_leakage':'REQUIRES_CLAIM_AUDIT','verdict_mode':'AI_RULE_CHECK_NOT_HUMAN'})
            if chunks:assert covered==len(evidence) and overlap==t1-t0
    result={'status':'SCOPE_AND_BODY_VISIT_DIAGNOSTIC','rows':rows,
        'scope_runs_identical':'same frozen selections/partitions across3 repeats; A recomputed per unit',
        'total_gold_bound_regions_per_round':sum(len(bindings(q)) for q in gold.values()),
        'warning':'Target-region precision is context-access diagnostic; not scope-selection correctness. P0 source spans unknown. Heading metadata separate.'}
    (profile/'scope-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if progress is not None:
        progress({'A_scope_question_checks':6,'A_and_S_target_region_access_recall':1.0,
                     'gold_regions':result['total_gold_bound_regions_per_round']})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',required=True,type=Path);p.add_argument('--gold',required=True,type=Path)
    a=p.parse_args();audit(a.profile.resolve(),a.gold.resolve(), progress=lambda event: print(json.dumps(event)))
