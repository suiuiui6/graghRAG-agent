# Paper Annotation Protocol

## 1. Purpose and Scope

This protocol defines the manual annotation and review policy for the evaluation set in [ground_truth.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/ground_truth.json).

Its purpose is to give one stable interpretation for:

- `expected_node_ids`
- `expected_keywords`
- `forbidden_keywords`
- `should_refuse`
- false-premise handling
- `reasoning_hops`
- ambiguity notes

The goal is not to eliminate all subjectivity. The goal is to make the remaining subjectivity explicit, bounded, and auditable.

## 2. Evidence Sources and Unit of Annotation

The annotation evidence source is the frozen document evidence represented by:

- the KG nodes
- the linked document-derived chunks
- the recorded evidence pages in the GT set

The basic annotation unit is the question-level sample.

The annotation target is not a free-text span. It is a question record with structured fields that can support retrieval, answer-support, refusal, and robustness evaluation.

Node granularity rule:

- annotate at the KG node level, not at arbitrary text-span level

## 3. Field Definitions

### 3.1 Field overview

| Field | Type | What it records | Inclusion rule | Exclusion rule | Typical size | Example note |
|---|---|---|---|---|---|---|
| `expected_node_ids` | `list[str]` | Minimum sufficient KG nodes that support a correct answer | Include nodes required to justify the target answer or correction | Exclude merely related, background, or redundant nodes | `0-5` | For refusal items this may be empty |
| `expected_keywords` | `list[str]` | Acceptable answer cues used for lexical checks | Include canonical terms, aliases, bilingual variants, decisive numbers | Exclude stylistic filler and overly specific phrasing | `1-6` | May contain Chinese and English variants |
| `forbidden_keywords` | `list[str]` | High-risk distractors that should not appear in a concise correct answer | Include confusable numbers, wrong entities, wrong scenario labels | Exclude broad neighboring concepts unless truly misleading | `0-3` | Used for contamination checks |
| `should_refuse` | `bool` | Whether the system should refuse to answer from the document evidence | Mark `true` for unsupported or out-of-scope requests | Mark `false` when the document supports an answer or correction | binary | T5 are usually `true`; T7 are not always |
| `false_premise` | `bool` | Whether the question contains a materially wrong presupposition | Mark `true` when the question embeds a false claim that should be corrected | Mark `false` for ordinary unsupported questions | binary | Distinguishes correction from plain refusal |
| `reasoning_hops` | `int` | Minimum evidence-composition depth needed for a justified answer | Count the smallest number of linked evidence steps needed | Do not count redundant search behavior | usually `1-2` | Current set effectively uses `1` or `2` |
| `evidence_pages` | `list[int]` | Pages where decisive evidence appears | Include pages containing the supporting node content | Exclude pages with only loose mentions | `1-3` | Page indices follow the current dataset convention |
| `notes` | `str` | Free-text adjudication note for ambiguity or exceptions | Record boundary choices and unresolved alternates | Do not restate obvious content already encoded above | short text | Required when ambiguity may affect metrics |

### 3.2 Concrete protocol rules by field

| Field | Concrete protocol text |
|---|---|
| `expected_node_ids` | Define this as the minimum sufficient node set, not the maximum related node set. Equivalent but unlisted nodes may still support a semantically correct answer. |
| `expected_keywords` | Define these as answer-acceptance anchors for lexical coverage, not as a full reference answer. Include canonical Chinese forms, major aliases, and decisive numerals when exactness matters. |
| `forbidden_keywords` | Use this field to prevent answer contamination from nearby but wrong figures, entities, or scenario labels. |
| `should_refuse` | Define this as “the document does not provide enough evidence to answer as asked.” This follows the current T5 behavior. |
| `false_premise` | Define this as “the question contains a false assumption that should be corrected rather than accepted.” |
| `reasoning_hops` | Define this as the minimum hops in the gold evidence chain, not the observed tool-call depth in [raw_runs.jsonl](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl). |
| `ambiguity handling` | Prefer minimal sufficient evidence, record acceptable alternates in `notes`, and avoid forcing one rigid surface form when multiple semantically equivalent formulations are possible. |

## 4. Annotation Procedure

Apply the following procedure to each question:

1. Read the question and identify its task class.
2. Decide whether the item is answerable, refusal-only, or false-premise correction.
3. Locate the minimum sufficient evidence nodes.
4. Record `expected_node_ids` using the minimal-sufficient-evidence rule.
5. Record `expected_keywords` using canonical wording plus decisive numerals or aliases where needed.
6. Record `forbidden_keywords` only when nearby distractors are likely to contaminate a correct answer.
7. Assign `should_refuse`.
8. Assign `false_premise` if the question embeds a wrong presupposition that should be corrected.
9. Assign `reasoning_hops` from the shortest gold evidence chain.
10. Record `evidence_pages`.
11. Use `notes` to explain any ambiguity, alternate admissible node, or list-boundary choice.

## 5. Ambiguity Resolution Rules

| Ambiguity type | Rule |
|---|---|
| Equivalent nodes | If two or more nodes express the same fact at different granularities, annotate the smallest set of nodes sufficient to justify the answer. Put other acceptable nodes in `notes` as admissible alternates rather than inflating `expected_node_ids`. |
| Equivalent expressions | If different surface forms denote the same answer, list at least one canonical form and major aliases in `expected_keywords`. Treat bilingual variants, abbreviation/full-form pairs, and normalized number-unit variants as equivalent. |
| List boundaries | For “list all X” questions, include only items that belong to the target semantic class under the paper’s own wording. Do not extend the list using nearby but broader metrics, captions, or discussion text. When class membership is debatable, record the boundary rationale in `notes`. |
| Partial support | If the document supports only part of the asked proposition, do not mark the item as fully answerable. Mark `should_refuse=true` if the unsupported part is essential, or mark `false_premise=true` if the unsupported part is contradicted by document evidence. |
| False-premise vs refusal | Use `false_premise=true` when the document contains evidence that the premise is wrong and the correct response should actively correct it. Use plain refusal when the premise cannot be verified either way from the document. |
| Node vs wording mismatch | If a model answer is semantically correct but uses wording different from `expected_keywords`, treat this as a lexical-coverage limitation rather than an automatic semantic error. This is consistent with the current handling of Q10 and Q11 in [REPORT_FINAL.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md). |
| Exact numbers | For exact-number questions, include the decisive numeral in `expected_keywords` and place common confusable numbers in `forbidden_keywords` when neighboring metrics are likely to contaminate the answer. |
| Hop counts | Count hops from the shortest gold reasoning path only. A question is 1-hop if one directly sufficient node or one directly sufficient evidence unit answers it; it is 2-hop if two linked facts must be composed. Do not infer higher hops merely from long runtime traces. |
| Refusal with empty gold nodes | For T5-style refusals, `expected_node_ids` may be empty because the gold target is a behavior label rather than a fact node. The gold object is the refusal decision plus refusal-style wording cues. |

## 6. Category-Specific Notes

### T1-T4 answerable items

For T1-T4, the default assumption is:

- `should_refuse=false`
- `false_premise=false`

unless the question itself introduces a false assumption or unsupported extension.

### T5 refusal items

For T5:

- `should_refuse=true`
- `expected_node_ids` may be empty
- `expected_keywords` may be empty
- `notes` should explain why the requested information is unsupported by the document evidence

### T6 noise robustness items

For T6:

- preserve the same semantic target as the clean source question
- annotate typo or paraphrase rationale in `notes`
- do not create a new gold answer merely because the noisy wording changes surface form

### T7 false-premise items

T7 needs special care.

Current repository behavior implies two T7 subtypes:

1. refusal-style false premise
2. correction-style false premise

Examples from the current GT set:

- Q48 behaves like a refusal-style false premise and should keep `should_refuse=true`
- Q49 and Q50 behave like correction-style false premises and should keep `should_refuse=false` while requiring explicit correction evidence

Recommended rule:

- if the document directly contradicts the premise and supports a corrective answer, use `false_premise=true` and keep the sample answerable
- if the premise is unsupported and the safest behavior is refusal, use `false_premise=true` with `should_refuse=true`

## 7. Quality Control and Adjudication

Minimum quality-control standard:

- every item should receive one primary annotation pass
- every high-ambiguity item should receive a second review or structured self-audit
- every disputed boundary should be documented in `notes`

Priority review buckets:

- list questions
- figure-description questions
- exact-number questions with confusable distractors
- T5 refusal items
- T7 false-premise items

Recommended review questions:

- is the node set minimal and sufficient?
- is the question truly answerable as written?
- does the keyword list encode semantic anchors rather than one narrow phrasing?
- does the item need forbidden keywords because nearby figures are likely distractors?
- is the hop count based on gold evidence composition rather than runtime trace length?

## 8. Limitations and Claim Boundaries

This protocol reduces, but does not eliminate, annotation subjectivity.

In particular:

- `expected_node_ids` are manually back-constructed from the current KG and may omit semantically equivalent nodes
- list-type questions require human boundary judgments
- `expected_keywords` encode lexical anchors rather than every acceptable answer wording
- false-premise behavior spans both refusal-style and correction-style cases

Accordingly:

- retrieval recall against this gold set should be interpreted as a conservative lower bound
- keyword coverage should be interpreted as a surface-form proxy rather than a full semantic correctness metric
- category-level conclusions should be paired with sample-size awareness where the bucket is small

Despite these limits, the protocol still supports defensible claims about:

- reproducible evidence grounding
- refusal reliability
- false-premise correction behavior
- bounded interpretation of quality-cost trade-offs under a fixed evaluation surface
