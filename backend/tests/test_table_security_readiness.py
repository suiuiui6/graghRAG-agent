"""Real in-memory DuckDB security and structured recall contracts."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from table_index import TableIndex, _compile_conditions


@pytest.fixture
def table():
    index = TableIndex()
    index.ingest_section({'chunk_id': 'fixture', 'sheet_name': 'report',
                          'metadata': {'source_file': 'report.xlsx', 'source_format': 'xlsx'},
                          'table_json': {'headers': ['名称', '预算'],
                                         'rows': [["O'Brien", '10'], ['other', '20']]}})
    yield index
    index.conn.close()


@pytest.mark.parametrize('limit', ["1; DROP TABLE table_rows", '1', -1, True, None, 1.5, 1001, 2**63])
def test_limit_requires_nonnegative_integer_without_executing_sql(table, limit):
    with pytest.raises(ValueError):
        table.query(top_k=limit)
    assert table.count() == 4


@pytest.mark.parametrize('condition', [
    'column_value_numeric > 0; DROP TABLE table_rows',
    "column_name = '预算' OR 1=1", "column_name = '预算' -- comment",
    "column_name = (SELECT '预算')", "read_csv('untrusted.csv') IS NOT NULL",
    "column_name = '预算' /*comment*/", 'unknown_column = 1',
])
def test_conditions_reject_sql_programs_functions_comments_and_unknown_fields(table, condition):
    with pytest.raises(ValueError):
        table.query([condition])
    assert table.count() == 4


def test_eav_compound_predicates_bind_strings_and_numbers(table):
    result = table.query(["column_name = '预算' AND column_value_numeric >= 10",
                          "column_value_numeric < 20"])
    assert [(r['column_name'], r['column_value_numeric']) for r in result] == [('预算', 10.0)]
    quoted = table.query(["column_value = 'O''Brien'"])
    assert len(quoted) == 1 and quoted[0]['column_value'] == "O'Brien"


def test_wide_fallback_and_preference_are_observable(table):
    result = table.query(['"预算" = \'10\''])
    assert len(result) == 1 and result[0]['sheet_name'] == 'report'
    assert "O'Brien" in result[0]['column_value']
    assert table.query(['"预算" = \'10\''], prefer_wide=False) == []


def test_zero_limit_returns_no_rows(table):
    assert table.query(top_k=0) == []
    assert table.query(["column_value_numeric > 0"], top_k=0) == []


@pytest.mark.parametrize('operator,value,expected', [
    ('=', '1e1', [10.0]), ('!=', '20', [10.0]), ('<>', '20', [10.0]),
    ('>', '+10', [20.0]), ('>=', '20', [20.0]), ('<', '20', [10.0]),
    ('<=', '10', [10.0]), ('=', '-1', []),
])
def test_all_documented_comparison_operators_use_literal_values(table, operator, value, expected):
    result = table.query([f'column_value_numeric {operator} {value}'])
    assert [r['column_value_numeric'] for r in result] == expected


def test_boolean_precedence_parentheses_and_null_predicates(table):
    result = table.query(["(column_name = '预算' AND column_value_numeric = 10) OR column_value = 'other'"])
    assert {(r['column_name'], r['column_value']) for r in result} == {('预算', '10'), ('名称', 'other')}
    assert len(table.query(['column_value_numeric IS NULL'])) == 2
    assert {r['column_value_numeric'] for r in table.query(['column_value_numeric IS NOT NULL'])} == {10., 20.}


@pytest.mark.parametrize('conditions', [
    [], (), None, [''], [42], ['a = 1'] * 33, ['a' * 2049], ['a = 1 OR ' * 70 + 'a = 1'],
    ['(' * 18 + 'a = 1' + ')' * 18], ['a ='], ['a = 1 trailing'],
    ['(a = 1 extra)'], ['a IS FALSE'], ['a IS NOT FALSE'], ['a LIKE \'x\''],
    ['a = b'], ['a = 1e999'], ['a = @'], ["a = 'unclosed"],
])
def test_predicate_grammar_rejects_malformed_unbounded_and_nonliteral_programs(conditions):
    with pytest.raises(ValueError):
        _compile_conditions(conditions, {'a'})


def test_ingest_preserves_eav_context_for_unusual_identifiers_and_short_rows():
    index = TableIndex()
    try:
        index.ingest_section({'chunk_id': 'unusual', 'sheet_name': '1 bad"name',
                              'table_json': {'headers': ['first name', 'amount'],
                                             'rows': [['person', None], ['short'], ['extra', 1, 'ignored']]}})
        assert index.count() == 5
        rows = index.query(['"first_name" = \'short\''])
        assert len(rows) == 1 and rows[0]['sheet_name'] == 't_1_bad_name'
        assert json.loads(rows[0]['column_value']) == ['short', '']
        assert len(index.export_rows()) == 5
        assert index.get_stats() == {'total_rows': 5, 'unique_sheets': 1, 'wide_tables': 1}
    finally:
        index.conn.close()
