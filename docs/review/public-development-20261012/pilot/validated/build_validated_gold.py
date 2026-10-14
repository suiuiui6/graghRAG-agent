"""Parse frozen official files locally and bind development answer evidence. No network."""
from pathlib import Path
from xml.etree import ElementTree as ET
import copy
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
PILOT = ROOT.parent
RAW = PILOT / 'raw'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(name, obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=json.loads((RAW/'download-manifest.json').read_text(encoding='utf-8'))
for record in manifest['records']:
    assert sha(RAW/record['file'])==record['sha256'],record['file']
draft_path=PILOT/'questions-gold.draft.json'
questions=copy.deepcopy(json.loads(draft_path.read_text(encoding='utf-8'))['questions'])
raw_sha={'LCNC-HOME':sha(RAW/'ini-homing.html'),'NIST-8091':sha(RAW/'NIST.IR.8091.pdf')}

# XML parsing reads the complete XHTML and decodes numeric entities; external DTD not fetched.
tree=ET.fromstring((RAW/'ini-homing.html').read_bytes())
tag=lambda n:n.tag.rsplit('}',1)[-1]
parent={c:p for p in tree.iter() for c in p}
paths={tree:'/html[1]'}
for node in tree.iter():
    counters={}
    for child in node:
        name=tag(child); counters[name]=counters.get(name,0)+1
        paths[child]=paths[node]+f'/{name}[{counters[name]}]'
def ancestors(node):
    while node in parent:
        node=parent[node]
        yield node
def plain(node, pre=False):
    s=''.join(node.itertext())
    return s.strip() if pre else ' '.join(s.split())
selected={'h1','h2','h3','p','pre','tr','figcaption'}
blocks=[]; bynode={}; canonical=''
for node in tree.iter():
    if tag(node) not in selected or any(tag(a) in selected or tag(a) in {'head','script','style'} for a in ancestors(node)):continue
    if tag(node)=='tr':
        text=' | '.join(plain(c) for c in node if tag(c) in {'th','td'})
    else:text=plain(node,tag(node)=='pre')
    if not text:continue
    row=dict(block_id=len(blocks),tag=tag(node),xpath=paths[node],anchor=node.get('id'),text=text,start=len(canonical),end=len(canonical)+len(text))
    blocks.append(row);bynode[node]=row;canonical+=text+'\n\n'
(ROOT/'LCNC-HOME.canonical.txt').write_text(canonical,encoding='utf-8',newline='\n')
assert canonical.count('6.10. HOME_ABSOLUTE_ENCODER')==1
write_json('LCNC-HOME.blocks.json',blocks)

layout=ROOT/'NIST-8091.layout.txt'
proc=subprocess.run(['pdftotext','-layout',str(RAW/'NIST.IR.8091.pdf'),str(layout)],capture_output=True,text=True)
assert proc.returncode==0,proc.stderr
pdf=layout.read_text(encoding='utf-8')
parts=pdf.split('\f');assert parts[-1].strip()=='';parts=parts[:-1];assert len(parts)==17
pages=[];offset=0
for i,text in enumerate(parts):
    pages.append(dict(pdf_page_zero_based=i,pdf_page_one_based=i+1,start=offset,end=offset+len(text),text=text))
    offset+=len(text)+1
(ROOT/'NIST-8091.canonical.txt').write_text(pdf,encoding='utf-8',newline='\n')
write_json('NIST-8091.pages.json',pages)
hashes={sid:sha(ROOT/(sid+'.canonical.txt')) for sid in raw_sha}
texts={'LCNC-HOME':canonical,'NIST-8091':pdf}
anchors={n.get('id'):n for n in tree.iter() if n.get('id')}
def subblocks(node):return [bynode[n] for n in node.iter() if n in bynode]
def section(anchor):return subblocks(parent[anchors[anchor]])
def html_ev(rows, span=None):
    assert rows
    a,b=span if span else (rows[0]['start'],rows[-1]['end'])
    return dict(source_sha256=raw_sha['LCNC-HOME'],canonical_sha256=hashes['LCNC-HOME'],canonical_char_half_open=[a,b],
                locator_kind='XHTML_XPATH_AND_CANONICAL_CHARS',xpaths=[r['xpath'] for r in rows],quote=canonical[a:b])
def pdf_ev(a,b):
    page=pages[7]
    assert page['start']<=a<b<=page['end']
    return dict(source_sha256=raw_sha['NIST-8091'],canonical_sha256=hashes['NIST-8091'],canonical_char_half_open=[a,b],
                locator_kind='PDF_PAGE_AND_CANONICAL_CHARS',pdf_page_zero_based=7,pdf_page_one_based=8,printed_page_label='5',quote=pdf[a:b])
def find_block(rows,needle):
    matches=[r for r in rows if needle in r['text']]
    assert len(matches)==1,(needle,len(matches))
    return matches[0]
def pre_line_ev(row,needle):
    lines=row['text'].splitlines(keepends=True);pos=row['start'];found=[]
    for line in lines:
        if needle in line:found.append(html_ev([row],(pos,pos+len(line.rstrip('\r\n')))))
        pos+=len(line)
    assert len(found)==1,(needle,len(found))
    return found[0]

configs=section('_configuration')
nextheading=bynode[anchors['_home_search_vel']]['start']
intro=[r for r in configs if r['start']<nextheading]
table=next(n for n in tree.iter() if tag(n)=='table' and n.get('class')=='tableblock')
table_rows=[bynode[n] for n in table.iter() if n in bynode]
expected_table=[['Homing Type','HOME_SEARCH_VEL','HOME_LATCH_VEL','HOME_USE_INDEX'],['Immediate','0','0','NO'],['Index-only','0','nonzero','YES'],['Switch-only','nonzero','nonzero','NO'],['Switch and Index','nonzero','nonzero','YES']]
assert [r['text'].split(' | ') for r in table_rows]==expected_table
browser=json.loads((ROOT/'browser-dom.json').read_text(encoding='utf-8'))
assert browser['dom']['table']==expected_table
assert browser['javaScriptEnabled'] is False
scope_rows={
 'DEV-L01':intro,
 'DEV-L02':section('_home_absolute_encoder'),
 'DEV-L03':section('_home_search_vel')+section('_home_latch_vel')+section('_home_final_vel'),
 'DEV-L04':section('sec:homing-section'),
 'DEV-L05':section('_immediate_homing')}
examples=scope_rows['DEV-L04']
example_begin=find_block(examples,'Examples for a 3 joint system')['start']
scope_rows['DEV-L04']=[r for r in examples if r['start']>=example_begin]
page=pages[7]
bullets=list(re.finditer(r'^\uf0b7\s+',page['text'],re.M));assert len(bullets)==14
expected_names=[x['item'] for x in questions[-1]['gold_items']]
pdf_items=[]
for i,m in enumerate(bullets):
    end=bullets[i+1].start() if i+1<len(bullets) else page['text'].rfind('\n                                              5')
    assert end>m.start()
    end_text=page['text'][m.start():end].rstrip()
    start=page['start']+m.start();end=start+len(end_text)
    assert expected_names[i] in pdf[start:end],expected_names[i]
    pdf_items.append(pdf_ev(start,end))
list_begin=page['start']+page['text'].index('The performance criteria')
qual_text='incomplete list of the kinds of measures that are needed includes:'
qual_begin=page['start']+page['text'].index(qual_text)

for q in questions:
    sid=q['source_id'];qid=q['question_id']
    q['draft_provenance']={'file':'../questions-gold.draft.json','sha256':sha(draft_path),'old_scope':q.pop('scope')}
    q.pop('source_snapshot_sha256',None)
    q['source_sha256']=raw_sha[sid]
    q['canonical_sha256']=hashes[sid]
    q['status']='SOURCE_BOUND_CANDIDATE_PENDING_INDEPENDENT_REVIEW'
    q['review_kind']='AI source and visual review; independent AI review pending; not human Gold'
    if sid=='LCNC-HOME':q['scope']=html_ev(scope_rows[qid])
    else:q['scope']=pdf_ev(list_begin,pdf_items[-1]['canonical_char_half_open'][1])
    for i,x in enumerate(q['gold_items']):
        x['draft_evidence']=x.pop('evidence')
        if qid=='DEV-L01':ev=[html_ev([table_rows[i+1]]),html_ev([table_rows[0]])]
        elif qid=='DEV-L02':
            rows=scope_rows[qid]
            if i<3:ev=[pre_line_ev(next(r for r in rows if r['tag']=='pre'),f'HOME_ABSOLUTE_ENCODER = {i}')]
            else:ev=[html_ev([find_block(rows,'A HOME_IS_SHARED setting' if i==3 else 'A request to rehome')])]
        elif qid=='DEV-L03':
            anchor=['_home_search_vel','_home_latch_vel','_home_final_vel'][i]
            rows=section(anchor)
            if i==0:rows=[r for r in rows if r['tag']=='p'][:2]
            else:rows=[r for r in rows if r['tag']=='p']
            ev=[html_ev(rows)]
        elif qid=='DEV-L04':
            pre=[r for r in scope_rows[qid] if r['tag']=='pre'][i]
            prior=blocks[pre['block_id']-1]
            ev=[html_ev([prior,pre])]
            actual=[int(v) for v in re.findall(r'HOME_SEQUENCE\s*=\s*(-?\d+)',pre['text'])]
            assert actual==x['required_attributes']['values']
        elif qid=='DEV-L05':
            rows=scope_rows[qid];pre=next(r for r in rows if r['tag']=='pre')
            ev=[pre_line_ev(pre,x['item']+' =')]
            if i==4:ev.append(html_ev([find_block(rows,'omitting a HOME_SEQUENCE')]))
        else:ev=[pdf_items[i]]
        x['evidence']=ev
    if qid=='DEV-L01':q['attribute_header_evidence']=html_ev([table_rows[0]])
    if qid=='DEV-L03':
        q['question']+='对 HOME_SEARCH_VEL，另说明零值对搜索阶段的影响。'
    if qid=='DEV-N01':
        q['required_answer_qualifiers']=[{'claim':'列表不完整；只穷尽文中当前列表，不代表所有可能度量',
                                         'evidence':[pdf_ev(qual_begin,qual_begin+len(qual_text))]}]
    # Separate atomic attribute scores; group membership is an unordered set, values retain joint identities.
    for i,x in enumerate(q['gold_items']):
        atoms=[]
        for field,value in x['required_attributes'].items():
            if field=='example_or_meaning_components':
                atoms += [{'atom_id':f'{field}.{j+1}','expected':v,'match':'semantic_equivalent'} for j,v in enumerate(value)]
            elif field=='values':
                atoms += [{'atom_id':f'HOME_SEQUENCE.JOINT_{j}','expected':v,'match':'exact_numeric'} for j,v in enumerate(value)]
            else:atoms.append({'atom_id':field,'expected':value,'match':'exact_unordered_set' if field=='synchronized_joints' else 'semantic_or_exact_as_applicable'})
        for atom in atoms:atom['evidence']=copy.deepcopy(x['evidence'])
        x['scoring_atoms']=atoms
    q['scope_semantics']='Gold target region; retrieval may use supporting context outside it, without adding off-scope answer items'

unit_records=[]
for sid in raw_sha:
    unit_records.append(dict(source_id=sid,raw_file='../raw/'+('ini-homing.html' if sid=='LCNC-HOME' else 'NIST.IR.8091.pdf'),
        source_sha256=raw_sha[sid],canonical_file=sid+'.canonical.txt',canonical_sha256=hashes[sid],
        coverage='complete HTML textual blocks, diagrams omitted' if sid=='LCNC-HOME' else 'complete 17-page pdftotext layout; figure contents not OCRed',
        scope='text-only development',full_text_scan_eligible=True,full_multimodal_scan_eligible=False,
        version='2.9 branch; footer 2026-10-11 09:59:50 UTC; byte hash is snapshot identity' if sid=='LCNC-HOME' else 'NISTIR 8091 November 2015',
        section_or_page_map='LCNC-HOME.blocks.json' if sid=='LCNC-HOME' else 'NIST-8091.pages.json'))
write_json('sources.json',unit_records)
payload=dict(schema_version='1.0',status='SOURCE_BOUND_CANDIDATE_PENDING_INDEPENDENT_REVIEW',
    dataset_role='development_only',human_gold_verified=False,questions=questions,heldout_H1=[],heldout_H2=[],
    intended_use='6 scope_given calibration probes, not generalization/novelty or automatic scope difficulty evidence',
    scoring={'surfaces':['scope selection separately','item precision and recall','required atomic attributes','runtime input evidence support'],
             'attributes':'Each scoring atom separately; no credit for an item name alone; record extras as false positives',
             'evidence':'Gold source evidence is not proof of runtime support; audit actual input receipts separately',
             'scope':'Report scope_given separately from any later scope_hidden tasks',
             'unit':'two source units; five same-page questions are correlated, not five independent documents',
             'fuzzy_grading':'semantic translations require adjudication; no automatic judge has been run'})
write_json('questions-gold.candidate.json',payload)
# Prevent accidental oracle leakage: model-facing questions contain no Gold offsets, counts or answers.
write_json('questions.input.json',[{'question_id':q['question_id'],'source_id':q['source_id'],'question':q['question'],'range_condition':q['range_condition']} for q in questions])
check=dict(status='LOCAL_SOURCE_BINDING_CHECKS_PASS_PENDING_INDEPENDENT_REVIEW',questions=len(questions),
 items=sum(len(q['gold_items']) for q in questions),attribute_atoms=sum(len(x['scoring_atoms']) for q in questions for x in q['gold_items']),
 qualifiers=sum(len(q.get('required_answer_qualifiers',[])) for q in questions),nist_pages=len(parts),nist_list_bullets=len(bullets),
 nist_list_pdf_page=8,nist_list_printed_page='5',browser_table_matrix_exact=True,raw_hash_guard=True,
 parser='Python stdlib ElementTree + Poppler pdftotext 25.07.0 -layout',pdftotext_stderr=proc.stderr,
 source_sha256=raw_sha,canonical_sha256=hashes)
for q in questions:
    t=texts[q['source_id']]
    for x in [q['scope']]+[e for item in q['gold_items'] for e in item['evidence']]+[e for item in q.get('required_answer_qualifiers',[]) for e in item['evidence']]:
        a,b=x['canonical_char_half_open'];assert t[a:b]==x['quote']
        assert x['source_sha256']==raw_sha[q['source_id']]
    assert q['expected_item_count']==len(q['gold_items'])
write_json('verification.candidate.json',check)
print(json.dumps(check,ensure_ascii=False))
