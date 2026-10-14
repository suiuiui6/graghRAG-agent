"""Read-only comparison of captured local PDF extraction modes, with an audit output."""
from pathlib import Path
import json,re,hashlib
root=Path(__file__).resolve().parent
a=(root/'NIST-8091.canonical.txt').read_text(encoding='utf-8').split('\f')[7]
b=(root/'NIST-8091.default.txt').read_text(encoding='utf-8').split('\f')[7]
norm=lambda s:re.sub(r'\s+','',s)
assert norm(a)!=norm(b), 'Expected observed bullet-position difference changed; inspect sources'
assert norm(a.replace('\uf0b7',''))==norm(b.replace('\uf0b7','')), 'Body text differs, inspect before admission'
assert a.count('\uf0b7')==b.count('\uf0b7')==14
assert len(re.findall(r'^\uf0b7\s+\S',a,re.M))==14
assert len(re.findall(r'^\uf0b7\s*$',b,re.M))==14
r=dict(status='PASS_BODY_CONTENT_WITH_CONFIRMED_DEFAULT_LIST_STRUCTURE_FAILURE',pdf_page_one_based=8,printed_page='5',
       body_equal_after_whitespace_and_bullet_position_ignored=True,bullet_count_both=14,
       default_mode='14 detached bullet-only lines before body items',layout_mode='14 bullets attached to item opening lines',
       adopted='pdftotext 25.07.0 -layout after visual review',scientific_interpretation='parser configuration issue, not new-method evidence',
       inputs={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['NIST-8091.canonical.txt','NIST-8091.default.txt']})
(root/'parser-comparison.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r,ensure_ascii=False))
