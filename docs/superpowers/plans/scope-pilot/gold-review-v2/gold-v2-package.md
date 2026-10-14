# Gold v2 local reproduction package

## scope_and_inputs

This is the bounded output of `GOLD-PACKAGE-20261008`, project `graphrag-paper-001`, paper family `M`, stage `M2`. The task, accepted policy record, versioned proposal, separate gpt-6.1-sol AI source review and its expert contract, unchanged old Gold and three supplied Markdown sources were read. No old participant answer or adjudication was read.

The task identity is preserved. Creation date is 2026-10-08 UTC, measured by the clock at `2026-10-08 00:06:46 UTC`. The inherited policy says author “继续” permits local v2 preparation and read-only preflight. It does not authorize a new API batch. This specialist owns only `gold-v2.yaml`, this Markdown and `gold-v2-package-contract.yaml`.

All source spans are zero-based Unicode code points in LF-normalized text, start inclusive and end exclusive. Use `Path.read_text(encoding="utf-8")` with universal newline conversion. Do not use UTF-8 byte or UTF-16 offsets. D3 contains non-BMP characters elsewhere, so those conventions are not interchangeable.

| Source | Original bytes SHA-256; also LF text SHA-256 for this snapshot | LF code points |
|---|---|---:|
| D1, `backend/output/mineru/ingest_2/full.md` | `f0e2b044ec0f8be55b1c00d9479830f6768a5da9970111a7db0353d59097a0d6` | 22366 |
| D2, `backend/output/mineru/ingest_f/full.md` | `ab7cdd99e8cd85ddd61e3d65e4e747685a25a62d22f68bed3e2d79d015e90623` | 42551 |
| D3, `integration/Agentic-RAG-Architecture.md` | `d0c64333bf10c761fef29bc1d9e002656f3968e720e176e92b8a18eb4a1e8e72` | 17729 |

## specialist_findings

The new Gold has nine versioned questions and the original 31 core item IDs. Every item has a structured `required_attributes` list; each attribute records `key`, `expected`, `evidence_class` and explicitly associated `evidence`. Every supporting evidence object has source identity, `start`, `end` and `exact_text`. YAML aliases reuse a full supporting sentence without removing attribute-specific associations. Optional attributes are separate.

| v2 question | Old qid | Core items | Complete local original interval |
|---|---|---|---|
| D1-FIG-v2 | D1-FIG; historical Q15 | F1–F6 | whole_document [0,22366) |
| D1-COST-v2 | D1-COST; historical Q16 | C1–C5 | section [55,1097) |
| D1-LIMITS-v2 | D1-LIMITS | L1–L4 | section [19694,20159) |
| D1-FUTURE-v2 | D1-FUTURE | R1–R2 | section [19694,20159), semantic target only [20059,20157) |
| D2-ATTENTION-v2 | D2-ATTENTION | A1–A3 | section [12251,13474) |
| D2-DATA-v2 | D2-DATA | T1–T2 | section [20861,21487) |
| D2-NONE-v2 | D2-NONE | empty set | section [12251,13474) |
| D3-TOOLS-v2 | D3-TOOLS | K1–K5 | section [6399,6809) |
| D3-SUPERVISOR-v2 | D3-SUPERVISOR | S1–S4 | section [11015,11170) |

For FIG, the complete local Markdown scan supports six unique figure numbers, six body captions and six Appendix B aliases. Body titles are primary; Appendix B aliases remain acceptable. Figure 2 remains 36吨/日. Unnumbered image links and the unnumbered `final_comprehensive.png` file do not add figure numbers. The full [0,22366) range is recorded with its hash and local materialization rule; the file does not reproduce private frontmatter as scope text. Section scopes include their complete exact text and hashes.

COST admits exactly the five direct 元/吨 levels 3554, 5820, 7111, 3669 and 5652 with problem, mode and applicable production/annual conditions. C1 does not require a 36吨/日 binding absent from its abstract sentence. C6-proposed (1970元/吨 grid-support economic value) and C7-proposed (2.9% relative reduction) appear only in old-question sensitivity records. C7 is optional C5 context in v2 and cannot be counted twice. Both are source-supported economic facts, so excluded membership alone does not make them fabrications. The abstract does not support importing the body's 1970 subtraction formula.

LIMITS keeps four numbered categories and separately encodes omitted factors, including both seasonal-load and seasonal-tariff omissions in L2. FUTURE keeps two alternative proposals joined by “或”; no implementation claim follows. The proposed uncertainty-set modelling measure is optional explanatory context, not a third family. FUTURE's provider-visible coverage/adjudication target is only complete item (4), D1 [20059,20157), with its own hash. Its wider [19694,20159) scope is optional reading context. A correctly mapped input containing all of item (4) is COMPLETE for this question without the other three limitations.

ATTENTION gives explicit Q/K/V sources separately for A1 and A2. A3 explicitly states visibility through the current position and masking illegal inputs of softmax to negative infinity. Its exact prior-decoder-layer Q/K/V source is not explicitly restated in §3.2.3. The three absence-labelled source-status attributes are supported by the complete scope, with one scope-conscious caveat allowed to satisfy them. An optional decoder-side provenance explanation is labelled `inferred`, supported by the self-attention analogy, and never promoted to an explicit statement. DATA preserves “about”, sentence pairs for T1, sentences for T2, and WMT 2014 for both. NONE's empty-set proof covers all of §3.2.3 and does not claim the whole paper lacks an optimizer.

Required fields follow the approved query. FIG panel descriptions, COST scenario counts/compliance and C3/C4 annual-context diagnostics, the C5 numeric adjustment range and comparison reference, L2 scene-count and summer/winter examples, and FUTURE abbreviations/target explanations are optional. Either recorded body title or Appendix B alias can satisfy strict FIG title judgment. Optional omissions do not lower required completeness; asserted wrong details are recorded as contradictions. Role fields are semantic judgments, and answers need not print normalization enums. The package has 125 required and 25 optional attributes.

Manual adjudication records content, actual-input support, scope coverage, citation entailment, negative behaviour and role separately. The required coverage algorithm selects `question.coverage_adjudication_target` when present, otherwise `question.scope`; optional wider reading context does not enlarge the mandatory target. A matching anchor or ID does not prove a semantic answer correct. Correct document memory cannot replace supporting input. Missing or partial required target context is `INSUFFICIENT_EVIDENCE` for complete-set/absence assertions. Architecture rows and responsibilities remain specifications, not verified live implementation facts. No aggregate accuracy or automatic semantic scorer is supplied.

## evidence_and_execution_status

`VERIFIED_USER_MATERIAL` applies to checked Markdown statements and complete-scope absence inspection. `AI_INFERENCE` applies only to the optional A3 provenance interpretation. `EXECUTED_LOCAL` applies to actual source hashes, range binding and schema checks. Original PDF visual verification and independent human annotation remain `PENDING_VERIFICATION`. Model/API execution, rendering, indexing, deposition and stage acceptance were `NOT_EXECUTED`.

A read-only Python inline command used the already installed `backend/.venv/Scripts/python.exe` and PyYAML 6.0.3; no installation or production/model import occurred. The first source print hit the Windows GBK stdout encoding limitation; rerunning with UTF-8 stdout succeeded. This affected only displayed output, not source spans or file contents.

Reproduce from the project root in PowerShell with the following command. It reads the package and its declared source/provenance files; it writes no script, output file or cache, and does not contact a provider:

```powershell
@'
from pathlib import Path
import sys,json,hashlib,yaml,re
sys.stdout.reconfigure(encoding='utf-8')
base=Path('docs/superpowers/plans/scope-pilot/gold-review-v2')
g=yaml.safe_load((base/'gold-v2.yaml').read_text(encoding='utf-8'))
old=yaml.safe_load((base.parent/'gold.yaml').read_text(encoding='utf-8'))
texts={d:Path(v['path']).read_text(encoding='utf-8') for d,v in g['documents'].items()}
for d,v in g['documents'].items():
 assert hashlib.sha256(Path(v['path']).read_bytes()).hexdigest()==v['sha256']
 assert hashlib.sha256(texts[d].encode()).hexdigest()==v['normalized_text_sha256']
 assert len(texts[d])==v['normalized_codepoint_length']
assert hashlib.sha256((base.parent/'gold.yaml').read_bytes()).hexdigest()==g['provenance']['old_gold_sha256']
for inp in g['provenance']['inputs']:assert hashlib.sha256(Path(inp['path']).read_bytes()).hexdigest()==inp['sha256']
expected={q['id']:set(i['id'] for i in q['items']) for q in old['questions']}
span_count=0;attribute_count=0;classes={}
for q in g['questions']:
 assert q['id']==q['original_qid']+'-v2'
 assert set(q['expected_item_ids'])==set(i['id'] for i in q['items'])==expected[q['original_qid']]
 s=q['scope'];t=texts[q['doc']]
 assert isinstance(s['start'],int) and isinstance(s['end'],int) and 0<=s['start']<s['end']<=len(t)
 assert hashlib.sha256(t[s['start']:s['end']].encode()).hexdigest()==s['text_sha256']
 if 'exact_text' in s:assert t[s['start']:s['end']]==s['exact_text']
 if 'coverage_adjudication_target' in q:
  target=q['coverage_adjudication_target']
  assert target['doc']==q['doc'] and s['start']<=target['start']<target['end']<=s['end']
  assert hashlib.sha256(t[target['start']:target['end']].encode()).hexdigest()==target['text_sha256']
  assert [target['start'],target['end']]==[20059,20157]
 for it in q['items']:
  assert it['id']==it['original_item_id']
  keys=[]
  for a in it['required_attributes']+it['optional_attributes']:
   assert set(['key','expected','evidence_class','evidence']).issubset(a)
   assert a['evidence_class'] in ['explicit','inferred','absence']
   assert a['evidence']
   keys.append(a['key']);attribute_count+=1;classes[a['evidence_class']]=classes.get(a['evidence_class'],0)+1
   for e in a['evidence']:
    assert e['doc']==q['doc']
    assert s['start']<=e['start']<e['end']<=s['end']
  assert len(keys)==len(set(keys))
 if q['original_qid']=='D2-NONE':
  assert q['items']==[]
  assert q['empty_set_proof']['evidence_class']=='absence'
  assert q['empty_set_proof']['evidence'][0]['start']==s['start']
  assert q['empty_set_proof']['evidence'][0]['end']==s['end']
def visit(v):
 global span_count
 if isinstance(v,dict):
  if set(['doc','start','end','exact_text']).issubset(v):
   assert isinstance(v['start'],int) and isinstance(v['end'],int)
   assert texts[v['doc']][v['start']:v['end']]==v['exact_text']
   span_count+=1
  for x in v.values():visit(x)
 elif isinstance(v,list):
  for x in v:visit(x)
visit(g)
f=next(q for q in g['questions'] if q['original_qid']=='D1-FIG')
assert f['scope']['start']==0 and f['scope']['end']==len(texts['D1'])
allcapt=[x for x in texts['D1'].splitlines() if re.match(r'^图\s+\d+',x)]
numbers=[int(re.match(r'^图\s+(\d+)',x).group(1)) for x in allcapt]
assert len(allcapt)==12 and sorted(set(numbers))==[1,2,3,4,5,6]
assert all(numbers.count(n)==2 for n in range(1,7))
print(json.dumps({'result':'PASS','questions':len(g['questions']),'core_items':sum(len(q['items']) for q in g['questions']),'attributes_required_plus_optional':attribute_count,'required_attributes':sum(len(i['required_attributes']) for q in g['questions'] for i in q['items']),'optional_attributes':sum(len(i['optional_attributes']) for q in g['questions'] for i in q['items']),'evidence_classes':classes,'exact_evidence_associations_verified':span_count,'source_hashes_verified':3,'input_hashes_verified':len(g['provenance']['inputs'])+1,'scopes_verified':len(g['questions']),'D1_FIG_original_interval':[0,len(texts['D1'])],'D1_numbered_caption_lines':12,'D1_unique_numbered_figures':6,'D2_NONE_complete_scope_verified':True,'model_or_API_execution':False},ensure_ascii=False))
'@ | & backend/.venv/Scripts/python.exe -B -
```

Executed output, exit code 0:

```json
{"result": "PASS", "questions": 9, "core_items": 31, "attributes_required_plus_optional": 150, "required_attributes": 125, "optional_attributes": 25, "evidence_classes": {"explicit": 146, "absence": 3, "inferred": 1}, "exact_evidence_associations_verified": 172, "source_hashes_verified": 3, "input_hashes_verified": 6, "scopes_verified": 9, "D1_FIG_original_interval": [0, 22366], "D1_numbered_caption_lines": 12, "D1_unique_numbered_figures": 6, "D2_NONE_complete_scope_verified": true, "model_or_API_execution": false}
```

This proves structural and exact-source binding. It does not prove semantic scoring, corpus membership, current runtime identity or provider-visible completeness.

## deliverables

`gold-v2.yaml` is the local machine-readable source-bound package with nine queries, 31 items, attribute evidence, complete original ranges, fingerprints, old-ID crosswalks, title aliases, historical sensitivities, restrictions and the manual adjudication contract. `gold-v2-package-contract.yaml` is the exact 19-field expert return. This Markdown explains local reproduction and its limits.

The inventory consists of the three original Markdown sources, processed Gold, its metadata and reproduction command. PDF/images, model artifacts and current corpus/runtime mapping were not acquired by this specialist. The availability statement is local internal retention under source rights and privacy restrictions. No external repository was selected or deposited into, no redistribution license was invented, and no DOI/accession exists for this package.

FAIR metadata is locally findable through version, paths, project and task ID; locally accessible to authorized workspace users; interoperable through YAML, hashes and Unicode/LF spans; and reusable through policy, evidence and manual decision records. External reuse still requires actual rights and release decisions. A future deposit checklist is recorded in YAML: obtain rights, remove private identifiers, preserve original-to-export mapping and export hash, provide metadata/license, then record an identifier only after returned deposit evidence. There is no current manual action.

## limitations_and_risks

The evidence is supplied Markdown only. Original PDF figure completeness, visual layout, OCR fidelity and numerical calculations are not certified. This is an AI-assisted source package and a separate AI review, not independent human adjudication or a held-out blind test. The old Gold, 27 old answers and old adjudication are preserved under their own semantics.

D1's private frontmatter has not been authorized for provider transmission. A whole-document oracle scope is not upload permission. Any future approved transfer needs a separate redacted copy, its hash, exact original-to-redacted coordinates and explicit provider approval; those are not present. D2's third-party full text cannot be publicly republished by this package. D3 remains internal. No participant identifier or credential is copied into the three deliverables.

The legacy `pilot.py` is not v2 compatible. New IDs, structured attributes, numeric scopes, absence proofs and whole-document FIG handling require a future approved adapter. This package does not supply or claim that adapter. A future context assembler must perform a complete-document scan or create a source-supported caption inventory projection with a verifiable complete-scan coverage proof. The old six-appendix projection alone cannot prove all-document coverage. An 8192-byte cap cannot be presumed to hold this complete D1 document; any truncation or missing original-range mapping must be marked PARTIAL. Local Gold scope completeness and actual provider-visible input completeness are separate measurements.

Runtime identity, corpus mapping, new-batch permission, human annotation, PDF visual review and redacted export/mapping remain missing for future evaluation. They do not prevent this bounded local package from being reviewed. Gold scopes/expected items are oracle and adjudication material and must not be passed to AUTO resolution or model requests. M2 remains open; PASS_CANDIDATE here concerns only this package.

## quality_checks

Local checks passed for nine question IDs and complete original scopes, all 31 old-item crosswalks, three original/normalized source fingerprints, five upstream artifact hashes plus unchanged old Gold, 150 required-plus-optional attributes and 172 exact evidence associations. All evidence offsets and strings matched the LF/code-point slices; every attribute evidence lies within its question scope. The figure scan found twelve numbered caption/alias lines and six unique figure numbers. NONE's absence proof covers its whole target range. Required/optional keys are unique per item.

The companion contract's exact 19 top-level fields, task identity and output paths are separately checked after creation. The Markdown uses the seven specialist sections required by the skill. No source, old Gold, stage/state, approval or production code was edited.

## one_next_action

The orchestrator should review and accept this local source-bound v2 package together with the execution preflight, while retaining M2 as open and keeping any new API batch subject to separate authorization.
