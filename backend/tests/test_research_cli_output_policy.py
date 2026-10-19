"""Research libraries remain silent; explicit command entry points own stdout."""
import importlib.util
import json
from pathlib import Path

import pytest
import ast


def policy_module():
    spec = importlib.util.spec_from_file_location("cli_print_policy", Path(__file__).with_name("test_error_handling_policy.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code", [
    "def main(value=print('import')):\n    print('command')\n",
    "@print('import')\ndef main():\n    print('command')\n",
    "def main() -> print('import'):\n    print('command')\n",
])
def test_main_definition_expressions_are_not_cli_output(code):
    assert list(policy_module()._library_print_lines(ast.parse(code), True)) == [1]


def test_registered_cli_only_allows_entrypoint_prints(tmp_path, monkeypatch):
    policy = policy_module()
    source = tmp_path / "research/common_scope_audit.py"
    source.parent.mkdir()
    source.write_text("def helper():\n    print('library leak')\ndef main():\n    print('CLI')\n    def hidden():\n        print('nested leak')\nif __name__ == '__main__':\n    main()\n    print('CLI end')\n", encoding="utf-8")
    monkeypatch.setattr(policy, "_sources", lambda: [(source, "research/common_scope_audit.py")])
    with pytest.raises(AssertionError, match=r"common_scope_audit.py:2") as exc:
        policy.test_library_modules_have_no_print()
    assert "common_scope_audit.py:6" in str(exc.value)
    assert "common_scope_audit.py:4" not in str(exc.value)
    assert "common_scope_audit.py:9" not in str(exc.value)


def test_unregistered_main_is_not_a_print_exemption(tmp_path, monkeypatch):
    policy = policy_module()
    source = tmp_path / "new.py"
    source.write_text("def main():\n    print('unregistered')\n", encoding="utf-8")
    monkeypatch.setattr(policy, "_sources", lambda: [(source, "research/new.py")])
    with pytest.raises(AssertionError, match="research/new.py:2"):
        policy.test_library_modules_have_no_print()


def test_guard_else_branch_is_library_code(tmp_path, monkeypatch):
    policy = policy_module()
    source = tmp_path / "cli.py"
    source.write_text("if __name__ == '__main__':\n    print('command')\nelse:\n    print('import leak')\n", encoding="utf-8")
    monkeypatch.setattr(policy, "_sources", lambda: [(source, "research/common_scope_audit.py")])
    with pytest.raises(AssertionError, match="common_scope_audit.py:4"):
        policy.test_library_modules_have_no_print()


def scope_fixture(tmp_path):
    def save(rel, value):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    save("registration.json", {"work": [], "sources": {}})
    save("out/profile-status.json", {"status": "FINISHED"})
    save("fixture-gold.json", {"questions": []})
    return tmp_path / "fixture-gold.json"


def test_scope_helper_is_silent_and_callback_preserves_json_artifact(tmp_path, capsys):
    from research.common_scope_audit import audit
    gold = scope_fixture(tmp_path)
    result = audit(tmp_path, gold)
    assert capsys.readouterr().out == ""
    before = (tmp_path / "scope-audit.json").read_bytes()
    events = []
    assert audit(tmp_path, gold, progress=events.append) == result
    assert (tmp_path / "scope-audit.json").read_bytes() == before
    assert events == [{"A_scope_question_checks": 6, "A_and_S_target_region_access_recall": 1.0, "gold_regions": 0}]


def test_scope_cli_stdout_golden(tmp_path, monkeypatch, capsys):
    import runpy
    import sys
    from research import common_scope_audit
    gold = scope_fixture(tmp_path)
    monkeypatch.setattr(sys, "argv", ["common_scope_audit", "--profile", str(tmp_path), "--gold", str(gold)])
    runpy.run_path(common_scope_audit.__file__, run_name="__main__")
    assert capsys.readouterr().out == '{"A_scope_question_checks": 6, "A_and_S_target_region_access_recall": 1.0, "gold_regions": 0}\n'


def test_packet_helper_returns_none_and_preserves_generated_answers(tmp_path, capsys):
    """Synthetic local records only: no historical assessment/Gold is read."""
    from research.common_evaluation_packets import prepare, save, load
    schedule = []
    for i in range(54):
        row = {"unit_id": f"unit-{i}", "question_id": f"Q{i % 6}", "arm": ("A", "S", "P0")[i % 3], "repeat": i // 18}
        schedule.append(row)
        save(tmp_path / f"out/units/unit-{i}/result.json", {"unit_id": row["unit_id"], "status": "COMPLETED", "answer": f"synthetic answer {i}"})
    save(tmp_path / "registration.json", {"schedule": schedule})
    save(tmp_path / "out/profile-status.json", {"status": "FINISHED"})
    questions = []
    for i in range(6):
        items = []
        for j in range(6):
            count = 3 if i * 6 + j < 9 else 2
            items.append({"item": f"synthetic item {j}", "scoring_atoms": [{"atom_id": f"a{k}", "expected": "synthetic"} for k in range(count)]})
        questions.append({"question_id": f"Q{i}", "question": "synthetic?", "gold_items": items})
    save(tmp_path / "synthetic-gold.json", {"questions": questions})
    events = []
    assert prepare(tmp_path, tmp_path / "synthetic-gold.json", progress=events.append) is None
    assert capsys.readouterr().out == ""
    assert events == [{"answers": 54, "unique_texts": 54}]
    packet = load(tmp_path / "evaluation/content-packet.json")
    assert len(packet["questions"]) == 6
    assert {row["answer"] for row in packet["answers"]} == {f"synthetic answer {i}" for i in range(54)}
    assert load(tmp_path / "evaluation/packet-freeze.json")["scoring_atoms_per_repeat_arm"] == 81
