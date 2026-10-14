"""Local software/source-binding checks, not human Gold certification."""
import copy
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def tool():
    assert (ROOT / 'backend/research/gold_v2.py').exists(), 'v2 loader not implemented'
    return importlib.import_module('backend.research.gold_v2')


def test_frozen_package_counts():
    package = tool().load_gold(ROOT)
    assert package.summary == {'questions': 9, 'core_items': 31,
                               'required_attributes': 125, 'optional_attributes': 25,
                               'exact_evidence_associations': 172, 'source_documents': 3}


def test_future_coverage_uses_numbered_target():
    m = tool()
    p = m.load_gold(ROOT)
    q = next(q for q in p.data['questions'] if q['id'] == 'D1-FUTURE-v2')
    assert m.coverage_status(q, [('D1', 20059, 20157)]) == 'COMPLETE'
    assert m.coverage_status(q, [('D1', 20059, 20156)]) == 'PARTIAL'
    assert m.coverage_status(q, [('D2', 20059, 20157)]) == 'MISSING'


@pytest.mark.parametrize('mutation', ['version', 'span', 'evidence', 'duplicate', 'optional'])
def test_schema_and_source_drift_rejected(mutation):
    m = tool()
    p = m.load_gold(ROOT)
    data = copy.deepcopy(p.data)
    if mutation == 'version':
        data['version'] = '1.0'
    elif mutation == 'span':
        data['questions'][0]['scope']['start'] = -1
    elif mutation == 'evidence':
        data['questions'][0]['items'][0]['required_attributes'][0]['evidence'][0]['exact_text'] = 'bad'
    elif mutation == 'duplicate':
        data['questions'][0]['items'].append(data['questions'][0]['items'][0])
    else:
        data['questions'][0]['items'][0]['optional_attributes'] = None
    with pytest.raises(m.GoldValidationError):
        m.validate_gold(data, p.texts)


def test_hash_and_path_guards():
    m = tool()
    with pytest.raises(m.GoldValidationError, match='HASH_MISMATCH'):
        m.verify_hash(b'changed', '0' * 64)
    with pytest.raises(m.GoldValidationError, match='PATH_OUTSIDE_ROOT'):
        m.local_path(ROOT, '../elsewhere.yaml')
    with pytest.raises(m.GoldValidationError):
        m.local_path(ROOT, ROOT / 'backend/config.py')


def test_unicode_newline_convention():
    m = tool()
    text = m.normalize_text('中\r\n😀\rX')
    assert text == '中\n😀\nX'
    assert text[2:3] == '😀' and len(text) == 5


def test_empty_set_requires_full_visible_scope():
    m = tool()
    p = m.load_gold(ROOT)
    q = next(q for q in p.data['questions'] if q['id'] == 'D2-NONE-v2')
    assert m.coverage_status(q, []) == 'MISSING'
    assert m.coverage_status(q, [('D2', 12251, 13000), ('D2', 13000, 13474)]) == 'COMPLETE'
    assert m.coverage_status(q, [('D2', 12251, 13000), ('D2', 13001, 13474)]) == 'PARTIAL'


def test_absence_proof_requires_exact_text():
    m = tool()
    p = m.load_gold(ROOT)
    data = copy.deepcopy(p.data)
    q = next(q for q in data['questions'] if q['id'] == 'D2-NONE-v2')
    q['empty_set_proof'] = copy.deepcopy(q['empty_set_proof'])
    del q['empty_set_proof']['evidence'][0]['exact_text']
    with pytest.raises(m.GoldValidationError, match='INVALID_ABSENCE_EVIDENCE'):
        m.validate_gold(data, p.texts)
