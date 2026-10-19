"""Offline boundary tests for the bounded pilot; synthetic source and credentials."""
import json
import shutil
import socket
import sys
from pathlib import Path

import pytest
import yaml

from research import deepseek_scope_pilot as pilot


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("external network forbidden")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def valid_plan():
    return {"guard_files": {}, "rows": [
        {"qid": f"Q{i}", "baseline": b,
         "payload": pilot.make_payload("source only", "D", "fact", [])}
        for i in range(9) for b in ("B1", "B2", "B3")]}


@pytest.mark.parametrize("field,value,error", [
    ("baseline", "B4", "INVALID_REQUEST_MATRIX"),
    ("messages", [], "INVALID_MESSAGES"),
    ("context", {"document": "D"}, "INVALID_CONTEXT_PAYLOAD"),
    ("context", {"document": "D", "query": "q", "source_contexts": [
        {"start": 0, "end": 1, "text": "a", "unapproved": True}]}, "INVALID_CONTEXT_SPANS"),
    ("context", {"document": "D", "query": "q", "source_contexts": [
        {"start": 0, "end": 4, "text": "参赛编号"}]}, "INVALID_CONTEXT_SPANS"),
    ("context", {"document": "D", "query": "q", "source_contexts": [
        {"start": 0, "end": 8193, "text": "x" * 8193}]}, "CONTEXT_BUDGET_EXCEEDED"),
])
def test_invalid_matrix_and_context_rejected_without_output(tmp_path, field, value, error):
    plan = valid_plan()
    if field == "baseline":
        plan["rows"][0][field] = value
    elif field == "messages":
        plan["rows"][0]["payload"][field] = value
    else:
        plan["rows"][0]["payload"]["messages"][1]["content"] = json.dumps(value)
    output = tmp_path / pilot.PILOT_DIR / "api-runs" / "invalid"
    with pytest.raises(pilot.PilotError, match=error):
        pilot.run(plan, tmp_path, output)
    assert not output.exists()


@pytest.mark.parametrize("guards,error", [(None, "INVALID_GUARDS"),
    ({"source.txt": "not-a-digest"}, "INVALID_GUARD_HASH")])
def test_guard_schema_rejection(tmp_path, guards, error):
    with pytest.raises(pilot.PilotError, match=error):
        pilot.verify_guards(tmp_path, guards)


@pytest.mark.parametrize("url,key,error", [
    ("http://api.deepseek.com", "synthetic", "OFFICIAL_BASE_URL_REQUIRED"),
    ("https://api.deepseek.com", " ", "PRIVATE_CREDENTIAL_REQUIRED"),
    ("https://api.deepseek.com/v1", "has space", "PRIVATE_CREDENTIAL_REQUIRED"),
])
def test_credential_policy_reads_only_injected_mapping(tmp_path, monkeypatch, url, key, error):
    import dotenv
    seen = []
    def fake(path, interpolate):
        assert path == tmp_path / "backend/.env" and interpolate is False
        seen.append(path)
        return {"LANGEXTRACT_BASE_URL": url, "LANGEXTRACT_API_KEY": key}
    monkeypatch.setattr(dotenv, "dotenv_values", fake)
    with pytest.raises(pilot.PilotError, match=error):
        pilot.credentials(tmp_path)
    assert len(seen) == 1


def preparation_fixture(root, mutation):
    folder = root / pilot.PILOT_DIR
    folder.mkdir(parents=True)
    original = Path(__file__).resolve().parents[2] / pilot.PILOT_DIR / "pilot.py"
    shutil.copyfile(original, folder / "pilot.py")
    source = root / "source.md"
    source.write_text("begin\nsupported fact\n" +
                      ("内容" * 2000 if mutation == "context_unready" else "") + "\nend",
                      encoding="utf8")
    gold = {"documents": {"D": {"path": "source.md", "sha256": pilot.digest(source.read_bytes())}},
            "questions": [{"id": f"Q{i}", "doc": "D", "query": "fact",
                "scope": {"kind": "section", "start": "begin", "end": "end"},
                "items": [{"id": "private-gold", "label": "fact", "value": "fact", "unit": "",
                           "condition": "", "role": "", "anchor": "supported fact"}]}
                for i in range(9)]}
    if mutation == "question_count":
        gold["questions"].pop()
    if mutation == "invalid_gold":
        gold["documents"]["D"]["sha256"] = "0" * 64
    (folder / "gold.yaml").write_text(yaml.safe_dump(gold), encoding="utf8")
    (folder / "inputs-B2.json").write_text(json.dumps({"system_instruction":
        "" if mutation == "instruction" else "source only"}), encoding="utf8")
    paths = ["source.md"] + [(pilot.PILOT_DIR / n).as_posix()
                             for n in ("pilot.py", "gold.yaml", "inputs-B2.json")]
    guards = {p: pilot.digest((root / p).read_bytes()) for p in paths}
    if mutation == "missing_source":
        del guards["source.md"]
    if mutation == "missing_pilot":
        del guards[(pilot.PILOT_DIR / "pilot.py").as_posix()]
    manifest = {"schema_version": 1, "guard_files": guards}
    if mutation == "schema":
        manifest["schema_version"] = 2
    if mutation == "run_spec":
        manifest["run_spec"] = {"max_requests": 28}
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf8")
    return path


@pytest.mark.parametrize("mutation,error", [
    ("schema", "INVALID_MANIFEST"), ("missing_pilot", "MISSING_PILOT_GUARDS"),
    ("run_spec", "RUN_SPEC_MISMATCH"), ("invalid_gold", "GOLD_VALIDATION_FAILED"),
    ("question_count", "EXACTLY_NINE_QUESTIONS_REQUIRED"),
    ("missing_source", "MISSING_SOURCE_GUARD"), ("instruction", "INVALID_SYSTEM_INSTRUCTION"),
    ("context_unready", "CONTEXT_NOT_READY"),
])
def test_preparation_rejects_invalid_registered_inputs(tmp_path, mutation, error):
    manifest = preparation_fixture(tmp_path, mutation)
    with pytest.raises(pilot.PilotError, match=error):
        pilot.prepare(tmp_path, manifest)
    assert not (tmp_path / pilot.PILOT_DIR / "api-runs").exists()


def test_surviving_spans_skip_disjoint_exclusion_and_fully_removed_part():
    text = "abcdefghi"
    parts = [{"start": 2, "end": 4}, {"start": 6, "end": 9}]
    exclusions = [{"start": 0, "end": 1}, {"start": 2, "end": 4}, {"start": 8, "end": 9}]
    assert pilot.surviving_spans(parts, text, exclusions) == [{"start": 6, "end": 8, "text": "gh"}]


def test_cli_validation_failure_has_static_error_and_no_provider(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pilot", "--manifest", str(tmp_path / "missing.json")])
    assert pilot.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "STOPPED: validation or local preparation failed\n"
