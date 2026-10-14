"""Frozen local Gold validation. Never used by the AUTO scope resolver.

No production imports, environment reads, network or semantic answer scoring.
Coordinates are LF-normalized Unicode codepoints, start inclusive/end exclusive.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import yaml

PACKAGE_DIR = 'docs/superpowers/plans/scope-pilot/gold-review-v2'
FROZEN_HASHES = {
    'gold-v2.yaml': '1b5aa18287aa6f39160acf580082a460b054b77b7b29e75bc9e566b8280a3619',
    'gold-v2-package.md': '64cdb08d71f24b880cbb95a6b8a4cc8bb7f2320cd206b6fad05f7c3ef1c681df',
    'gold-v2-package-contract.yaml': '8de13380d5751ef4b315645311966d3ceab6a2edec0209c0771d0ad546f28ec3',
}


class GoldValidationError(ValueError):
    """Safe metadata-only error: does not include source text."""


def require(condition, code):
    if not condition:
        raise GoldValidationError(code)


def normalize_text(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def verify_hash(raw, expected):
    require(isinstance(expected, str) and hashlib.sha256(raw).hexdigest() == expected,
            'HASH_MISMATCH')


def local_path(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    require(not path.is_absolute(), 'PATH_OUTSIDE_ROOT')
    result = (root / path).resolve()
    require(result.is_relative_to(root), 'PATH_OUTSIDE_ROOT')
    return result


@dataclass(frozen=True)
class GoldPackage:
    data: dict
    texts: dict
    summary: dict
    gold_sha256: str


def _span(obj, texts, default_doc=None):
    require(isinstance(obj, dict), 'INVALID_SPAN')
    doc = obj.get('doc', default_doc)
    require(doc in texts, 'UNKNOWN_DOCUMENT')
    start, end = obj.get('start'), obj.get('end')
    require(type(start) is int and type(end) is int and
            0 <= start < end <= len(texts[doc]), 'INVALID_SPAN')
    text = texts[doc][start:end]
    if 'text_sha256' in obj:
        verify_hash(text.encode('utf-8'), obj['text_sha256'])
    if 'exact_text' in obj:
        require(text == obj['exact_text'], 'EXACT_TEXT_MISMATCH')
    return doc, start, end


def validate_gold(data, texts):
    """Schema/source binding only. Use load_gold for authoritative frozen hashes."""
    require(isinstance(data, dict) and data.get('version') == '2.0', 'INVALID_VERSION')
    require(data.get('locator_convention', {}).get('normalization') == 'universal_newline_to_LF'
            and data['locator_convention'].get('index_unit') == 'Unicode_codepoint'
            and data['locator_convention'].get('start') == 'zero_based_inclusive'
            and data['locator_convention'].get('end') == 'exclusive', 'INVALID_COORDINATES')
    documents = data.get('documents')
    require(isinstance(documents, dict) and set(documents) == set(texts), 'INVALID_DOCUMENTS')
    for doc, info in documents.items():
        require(isinstance(info, dict), 'INVALID_DOCUMENT')
        verify_hash(texts[doc].encode('utf-8'), info.get('normalized_text_sha256'))
        require(len(texts[doc]) == info.get('normalized_codepoint_length'), 'SOURCE_LENGTH_MISMATCH')
    questions = data.get('questions')
    require(isinstance(questions, list) and len(questions) == data.get('core_question_count'),
            'INVALID_QUESTIONS')
    ids = set()
    items_count = required_count = optional_count = 0
    for q in questions:
        require(isinstance(q, dict) and isinstance(q.get('id'), str)
                and q['id'] not in ids, 'INVALID_QUESTION_ID')
        ids.add(q['id'])
        require(q.get('query_version') == '2.0' and isinstance(q.get('query'), str)
                and bool(q['query'].strip()), 'INVALID_QUERY')
        require(q['id'] == q.get('original_qid', '') + '-v2', 'INVALID_CROSSWALK')
        doc, start, end = _span(q.get('scope'), texts, q.get('doc'))
        if 'coverage_adjudication_target' in q:
            td, ts, te = _span(q['coverage_adjudication_target'], texts, doc)
            require(td == doc and start <= ts < te <= end, 'TARGET_OUTSIDE_SCOPE')
        items = q.get('items')
        require(isinstance(items, list), 'INVALID_ITEMS')
        item_ids = [i.get('id') for i in items if isinstance(i, dict)]
        require(len(item_ids) == len(items) and all(isinstance(i, str) for i in item_ids)
                and len(set(item_ids)) == len(item_ids)
                and item_ids == q.get('expected_item_ids'), 'INVALID_ITEM_IDS')
        items_count += len(items)
        for item in items:
            require(item['id'] == item.get('original_item_id'), 'INVALID_ITEM_CROSSWALK')
            required, optional = item.get('required_attributes'), item.get('optional_attributes')
            require(isinstance(required, list) and bool(required) and isinstance(optional, list),
                    'INVALID_ATTRIBUTES')
            required_count += len(required)
            optional_count += len(optional)
            keys = set()
            for attr in required + optional:
                require(isinstance(attr, dict) and {'key', 'expected', 'evidence_class', 'evidence'}
                        <= attr.keys(), 'INVALID_ATTRIBUTE')
                require(isinstance(attr['key'], str) and attr['key'] not in keys,
                        'DUPLICATE_ATTRIBUTE')
                keys.add(attr['key'])
                require(attr['evidence_class'] in ('explicit', 'inferred', 'absence')
                        and isinstance(attr['evidence'], list) and bool(attr['evidence']),
                        'INVALID_EVIDENCE_CLASS')
                for ev in attr['evidence']:
                    ed, es, ee = _span(ev, texts)
                    require('exact_text' in ev and ed == doc and start <= es < ee <= end,
                            'EVIDENCE_OUTSIDE_SCOPE')
        if not items:
            proof = q.get('empty_set_proof', {})
            require(isinstance(proof, dict) and proof.get('evidence_class') == 'absence'
                    and isinstance(proof.get('evidence'), list) and bool(proof['evidence']),
                    'MISSING_ABSENCE_PROOF')
            proof_spans = []
            for ev in proof['evidence']:
                require(isinstance(ev, dict) and 'exact_text' in ev, 'INVALID_ABSENCE_EVIDENCE')
                ed, es, ee = _span(ev, texts)
                require(ed == doc and start <= es < ee <= end, 'INVALID_ABSENCE_EVIDENCE')
                proof_spans.append((ed, es, ee))
            require((doc, start, end) in proof_spans, 'INCOMPLETE_ABSENCE_PROOF')
    require(items_count == data.get('core_item_count'), 'ITEM_COUNT_MISMATCH')
    evidence_count = 0

    def visit(value):
        nonlocal evidence_count
        if isinstance(value, dict):
            if {'doc', 'start', 'end', 'exact_text'} <= value.keys():
                _span(value, texts)
                evidence_count += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return {'questions': len(questions), 'core_items': items_count,
            'required_attributes': required_count, 'optional_attributes': optional_count,
            'exact_evidence_associations': evidence_count, 'source_documents': len(texts)}


def load_gold(root, gold_path=None, freeze_path=None):
    root = Path(root).resolve()
    directory = local_path(root, PACKAGE_DIR)
    gold_path = local_path(root, gold_path or f'{PACKAGE_DIR}/gold-v2.yaml')
    freeze_path = local_path(root, freeze_path or f'{PACKAGE_DIR}/local-freeze-v2-20261008.json')
    raw = gold_path.read_bytes()
    verify_hash(raw, FROZEN_HASHES['gold-v2.yaml'])
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    require(freeze.get('gold_sha256') == FROZEN_HASHES['gold-v2.yaml'] and
            freeze.get('status') == 'ACCEPTED_BY_ORCHESTRATOR_NOT_HUMAN_CERTIFICATION',
            'INVALID_FREEZE_RECORD')
    for name, expected in FROZEN_HASHES.items():
        verify_hash((directory / name).read_bytes(), expected)
    data = yaml.safe_load(raw.decode('utf-8'))
    texts = {}
    for doc, info in data['documents'].items():
        source_raw = local_path(root, info['path']).read_bytes()
        verify_hash(source_raw, info['sha256'])
        texts[doc] = normalize_text(source_raw.decode('utf-8'))
    prov = data['provenance']
    verify_hash(local_path(root, prov['old_gold_path']).read_bytes(), prov['old_gold_sha256'])
    for inp in prov['inputs']:
        verify_hash(local_path(root, inp['path']).read_bytes(), inp['sha256'])
    return GoldPackage(data, texts, validate_gold(data, texts), FROZEN_HASHES['gold-v2.yaml'])


def coverage_status(question, spans):
    """Actual visible source intervals only; not answer scoring or local scan proof."""
    target = question.get('coverage_adjudication_target', question['scope'])
    doc = target.get('doc', question['doc'])
    start, end = target['start'], target['end']
    relevant = []
    for source, a, b in spans:
        require(type(a) is int and type(b) is int and 0 <= a < b, 'INVALID_SPAN')
        if source == doc and a < end and b > start:
            relevant.append((max(a, start), min(b, end)))
    if not relevant:
        return 'MISSING'
    cursor = start
    for a, b in sorted(relevant):
        if a > cursor:
            return 'PARTIAL'
        cursor = max(cursor, b)
    return 'COMPLETE' if cursor >= end else 'PARTIAL'
