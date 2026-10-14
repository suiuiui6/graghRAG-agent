"""Deterministic TEST_ONLY fixtures; these are not scientific benchmark results."""
import importlib
import json
import math

import pytest


def synthetic_data():
    questions, runs = [], []
    for number in range(1, 51):
        category = ('T1' if number <= 12 else 'T2' if number <= 20 else
                    'T3' if number <= 28 else 'T4' if number <= 32 else
                    'T5' if number <= 42 else 'T6' if number <= 47 else 'T7')
        qid = f'Q{number:02d}'
        expected = [] if category == 'T5' else ['n0001', 'n0002']
        questions.append(dict(qid=qid, category=category, question='TEST_ONLY 测试问题',
                              expected_node_ids=expected, expected_keywords=['MILP', 'missing'],
                              forbidden_keywords=['bad'] if number % 2 else [],
                              should_refuse=category == 'T5', reasoning_hops=number % 3 + 1))
        answer = ('没有数据' if number % 2 else 'MILP bad 1 2 3') + (' 实际上' if number % 3 else '')
        if number == 48:
            answer = 'x' * 250
        tools = [dict(phase='request', name=name, args={'node_id': 'n0001'})
                 for name in ['get_entity_neighbors', 'get_entity_detail', 'search_kg_by_type'] * (number % 3 + 1)]
        tools.append(dict(phase='result', name='ignored'))
        runs.append(dict(qid=qid, category=category, query='TEST_ONLY', final_answer=answer,
                         retrieved_node_ids=['n0001'] if number % 2 else [],
                         answer_node_ids=['n0001', 'fake'] if number % 2 else [],
                         num_tool_calls=len(tools)-1, tool_calls=tools, latency_ms=number*10,
                         tokens={'input': number*100, 'output': number, 'total': number*101}))
    return {'questions': questions}, runs


def direct_paths(module, monkeypatch, tmp_path, gt, runs):
    for name in ('GT_PATH', 'RUNS_PATH', 'NODES_PATH', 'OUT_JSON', 'OUT_MD', 'OUT_REPORT'):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, tmp_path / name)
    if hasattr(module, 'GT_PATH'):
        module.GT_PATH.write_text(json.dumps(gt, ensure_ascii=False), encoding='utf-8')
    module.RUNS_PATH.write_text('\n' + '\n'.join(json.dumps(r, ensure_ascii=False) for r in runs) + '\n', encoding='utf-8')
    if hasattr(module, 'NODES_PATH'):
        module.NODES_PATH.write_text(json.dumps({'nodes': [{'node_id': 'n0001'}], 'node_count': 999}), encoding='utf-8')


@pytest.mark.parametrize('name', ['metrics_a1_retrieval', 'metrics_a2_faithfulness',
                                 'metrics_a3_robustness', 'metrics_a4_multihop', 'metrics_a5_performance'])
def test_real_metric_files_and_reports(name, monkeypatch, tmp_path):
    module = importlib.import_module(name)
    gt, runs = synthetic_data()
    direct_paths(module, monkeypatch, tmp_path, gt, runs)
    module.main()
    result = json.loads(module.OUT_JSON.read_text(encoding='utf-8'))
    if name == 'metrics_a1_retrieval':
        assert result['global']['recall_macro'] == pytest.approx(0.25)
        assert result['global']['excluded_qids_empty_expected'] == [f'Q{n:02d}' for n in range(33, 43)]
    elif name == 'metrics_a2_faithfulness':
        assert result['global']['n_questions_with_hallucination'] == 25
        assert len(result['forbidden_violation_inventory']) == 0
    elif name == 'metrics_a3_robustness':
        assert result['t5_refusal']['correct_refusal_rate'] == 0.5
        assert result['t5_refusal']['false_positive_answer_count'] == 5
        assert result['t6_robustness']['robustness_match_rate'] == 0.6
    elif name == 'metrics_a4_multihop':
        assert result['B_q31_outlier']['total_requests'] == 6
        assert result['B_q31_outlier']['repeated_call_signatures_count'] == 3
    else:
        assert result['global']['total_latency_ms'] == 12750
        assert result['latency_ms']['global']['p95'] == 480
        assert result['global']['total_input_tokens'] == 127500
    for attr in ('OUT_MD', 'OUT_REPORT'):
        if hasattr(module, attr):
            assert getattr(module, attr).read_text(encoding='utf-8').startswith('#')


def test_a1_set_semantics_and_order():
    import metrics_a1_retrieval as m
    row = m.per_question_metrics(['z', 'a', 'a'], ['a', 'b'])
    assert (row['precision'], row['recall'], row['mrr']) == (0.5, 0.5, 0.5)
    assert row['missing_expected'] == ['b']
    assert m.per_question_metrics([], ['a'])['f1'] == 0
    assert m.per_question_metrics(['a'], [])['recall'] is None
    assert m.macro_avg([None]) is None
    assert m.aggregate([])['n_with_expected'] == 0


@pytest.mark.parametrize('answer,refused', [('无', True), ('没有', True), ('answer', False)])
def test_a2_refusal_and_keyword_rules(answer, refused):
    import metrics_a2_faithfulness as m
    assert m._is_refusal(answer)[0] is refused
    assert m._keyword_hits(['W4S1', '图5', '20MW', 'absent'], 'wind 4 solar 1 图 5 20 MW')[0] == ['W4S1', '图5', '20MW']
    assert m._answer_snippet('') == ''
    assert m._answer_snippet('xxANCHORyy', 'ANCHOR', 1) == '…xANCHORy…'
    assert m._answer_snippet('abcd', 'missing', 1) == 'ab…'


def test_a2_missing_and_forbidden_inventory(monkeypatch, tmp_path):
    import metrics_a2_faithfulness as m
    gt = {'questions': [dict(qid='A', category='T5', question='test', forbidden_keywords=['bad']),
                        dict(qid='missing', category='T1', question='absent')]}
    direct_paths(m, monkeypatch, tmp_path, gt, [dict(qid='A', final_answer='bad')])
    m.main()
    result = json.loads(m.OUT_JSON.read_text(encoding='utf-8'))
    assert result['_meta']['missing_in_runs'] == ['missing']
    assert result['forbidden_violation_inventory'][0]['forbidden_hits'] == ['bad']
    assert not result['hallucinated_node_id_inventory']


def test_a3_missing_run_and_numeric_filter(monkeypatch, tmp_path):
    import metrics_a3_robustness as m
    direct_paths(m, monkeypatch, tmp_path, {'questions': [{'qid': 'missing'}]}, [])
    with pytest.raises(RuntimeError, match='missing'):
        m.main()
    assert not m.has_concrete_number_answer('n0001 第2页 page3 4 4')
    assert m.has_concrete_number_answer('1 2 3')
    assert m.contains_any('ABC', ['abc']) == (True, ['abc'])


def test_a4_empty_unknown_and_tools():
    import metrics_a4_multihop as m
    assert m.group_by_hops({'a': {}}, [{'qid': 'unknown'}, {'qid': 'a'}])['per_hops'] == {}
    assert m.q31_outlier_analysis({}) == {}
    assert m.t4_deep_dive({}, {}) == {'questions': []}
    assert m.t2_recall({}, {})['recall_mean'] == 0
    assert m.t2_recall({'Q13': {}}, {'Q13': {}})['questions'][0]['recall'] == 0
    assert m.tool_efficiency({}, [])['repeat_signature_ratio'] == 0
    assert m.hit_rate([], ['a']) == m.strict_hit([], ['a']) == 0
    assert m.precision_recall([], []) == (0, 0)
    assert m.strict_hit(['a'], ['a']) == 1
    assert m.tool_sequence([{'phase': 'request'}, {'phase': 'result'}]) == ['<unknown>']
    assert m.pearson([1], [2]) == m.pearson([1, 1], [2, 3]) == 0
    assert m.pearson([1, 2], [2, 4]) == pytest.approx(1)


def test_a5_percentile_cost_and_activity():
    import metrics_a5_performance as m
    assert math.isnan(m.percentile([], 90))
    assert m.percentile([3, 1, 2], 0) == 1
    assert m.percentile([3, 1, 2], 100) == 3
    assert m.percentile([3, 1, 2], 50) == 2
    assert m.dist([]) == {}
    assert m.dist([5])['stdev'] == 0
    assert math.isnan(m.pearson([], []))
    assert math.isnan(m.pearson([1, 1], [1, 2]))
    assert m.pearson([1, 2], [2, 4]) == pytest.approx(1)
    assert [m.bucket_label(n) for n in (1, 4, 11, 31)] == ['1-3', '4-10', '11-30', '31+']
    assert m.cost_usd(1000000, 1000000) == pytest.approx(1.37)
    assert m.activity_count({'activity_count': 0, 'num_tool_calls': 9}) == 0
    assert m.activity_count({'num_tool_calls': 3}) == 3
    assert m.activity_type({'activity_type': 'retrieved_sources'}) == 'retrieved_sources'


def test_helper_rejects_non_list_ids_without_losing_text_evidence():
    import run_inference_helpers as m
    assert m.extract_node_ids_from_text('') == []
    assert m.extract_retrieved_node_ids_from_rag_sources([
        {'entity_ids': 'n0001', 'metadata': {'entity_ids': 1},
         'properties': {'entity_ids': {}}, 'text': 'n0002', 'label': 5}],
        metadata={'pre_rerank_node_ids': 'not-a-list'}) == ['n0002']
    assert m.extract_retrieved_node_ids_from_rag_sources([], {'pre_rerank_node_ids': ['not-an-id']}) == []


def test_rewrite_missing_and_invalid_rows_are_reported(tmp_path):
    import conversation_rewrite_metrics as m
    assert m._normalize_node_ids(['', None, 'd1_n0001']) == ['n0001']
    assert m._macro([]) is None
    assert m._classify_eval_case(run={'error': 'timeout'}, gold_aliases=[],
                                 gold_alias_found_in_rewrite=[], gold_alias_found_in_sources=[],
                                 expected_node_ids_hit=[]) == ('execution_failure', 'request_failed')
    payload = m.build_metrics_payload(gt={'questions': [{}, {'qid': 'missing'}]}, runs=[{}],
                                      ground_truth_path=tmp_path/'gt', raw_runs_path=tmp_path/'runs', report_path=tmp_path/'report')
    assert payload['_meta']['missing_qids'] == ['missing']
    assert payload['global']['dataset_coverage_macro'] == 0
    assert 'missing' in m.build_report(payload)
    raw = tmp_path/'rows'
    raw.write_text('\n{}\n', encoding='utf-8')
    assert m._load_jsonl(raw) == [{}]


def test_a1_missing_runs_and_comparison_without_t6(monkeypatch, tmp_path):
    import metrics_a1_retrieval as m
    gt = {'questions': [dict(qid='a', category='T1', question='TEST_ONLY', expected_node_ids=['n0001']),
                        dict(qid='missing', category='T1', question='missing')]}
    direct_paths(m, monkeypatch, tmp_path, gt, [{'qid': 'a', 'retrieved_node_ids': ['n0001']}])
    m.main()
    result = json.loads(m.OUT_JSON.read_text(encoding='utf-8'))
    assert result['_meta']['missing_in_runs'] == ['missing']
    assert result['t1_vs_t6_delta']['delta_t6_minus_t1']['recall_macro'] is None
