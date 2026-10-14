"""Final local acceptance of already-reviewed development artifacts; no model/network."""
from pathlib import Path
import hashlib,json,re
import yaml

root=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((root/'freeze-manifest.json').read_text(encoding='utf-8'))
for row in freeze['files']:
    p=root/row['path']
    assert p.stat().st_size==row['bytes'],row['path']
    assert sha(p)==row['sha256'],row['path']
review=yaml.safe_load((root/'expert-result.yaml').read_text(encoding='utf-8'))
for name,h in review['reviewed_sha256'].items():assert sha(root/name)==h,name
candidate=json.loads((root/'questions-gold.candidate.json').read_text(encoding='utf-8'))
gold=json.loads((root/'questions-gold.v1.json').read_text(encoding='utf-8'))
assert sha(root/'questions-gold.candidate.json')==gold['reviewed_candidate_sha256']==freeze['reviewed_candidate_sha256']
assert gold['human_gold_verified'] is False
assert len(gold['questions'])==6
sources={s['source_id']:s for s in json.loads((root/'sources.json').read_text(encoding='utf-8'))}
texts={sid:(root/s['canonical_file']).read_text(encoding='utf-8') for sid,s in sources.items()}
for sid,s in sources.items():
    assert sha(root/s['raw_file'])==s['source_sha256']
    assert sha(root/s['canonical_file'])==s['canonical_sha256']
count=0
for c,q in zip(candidate['questions'],gold['questions'],strict=True):
    assert {k:v for k,v in c.items() if k not in {'status','review_kind'}}=={k:v for k,v in q.items() if k not in {'status','review_kind'}},q['question_id']
    source=sources[q['source_id']];text=texts[q['source_id']]
    scope=q['scope'];a,b=scope['canonical_char_half_open']
    evs=[scope]+[e for item in q['gold_items'] for e in item['evidence']]+[e for item in q['gold_items'] for atom in item['scoring_atoms'] for e in atom['evidence']]+[e for item in q.get('required_answer_qualifiers',[]) for e in item['evidence']]
    if 'attribute_header_evidence' in q:evs.append(q['attribute_header_evidence'])
    for ev in evs:
        x,y=ev['canonical_char_half_open']
        assert 0<=a<=x<y<=b<=len(text)
        assert text[x:y]==ev['quote']
        assert ev['source_sha256']==source['source_sha256']
        assert ev['canonical_sha256']==source['canonical_sha256']
        count+=1
    assert q['human_annotation_verified'] is False
    assert q['range_condition']=='scope_given'
inputs=json.loads((root/'questions.input.json').read_text(encoding='utf-8'))
for inp,q in zip(inputs,gold['questions'],strict=True):
    assert set(inp)=={'question_id','source_id','question','range_condition'}
    assert all(inp[k]==q[k] for k in inp)
assert sum(len(q['gold_items']) for q in gold['questions'])==36
assert sum(len(i['scoring_atoms']) for q in gold['questions'] for i in q['gold_items'])==81
assert sum(len(q.get('required_answer_qualifiers',[])) for q in gold['questions'])==1
report=root.parents[2]/'2026-10-12-public-development-gold-validation.md'
assert report.is_file(),report
for target in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
    if not target.startswith('http'):assert (report.parent/target).is_file(),target
result=dict(status='PASS_FOR_LOCAL_DEVELOPMENT_GOLD_V1',verified_on='2026-10-13',
    frozen_files_checked=len(freeze['files']),independent_review_hashes_checked=len(review['reviewed_sha256']),
    source_units=2,questions=6,items=36,attribute_scoring_units=81,required_qualifiers=1,
    evidence_bindings_checked=count,reviewed_answer_content_unchanged=True,model_input_has_no_gold=True,
    human_gold_verified=False,heldout_H1=[],heldout_H2=[],stage='M2_OPEN',model_experiment='NOT_EXECUTED',
    gold_sha256=sha(root/'questions-gold.v1.json'),freeze_manifest_sha256=sha(root/'freeze-manifest.json'))
(root/'final-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
