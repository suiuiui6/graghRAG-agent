"""Real local report algorithms over synthetic, hash-bound public-shaped inputs.

No provider request, historical research receipt, private source, or Gold is read.
"""
import hashlib
import json
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("These report tests must not access the network")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def wire_record(body="synthetic input", output="synthetic output", *, phase="a", qid="Q1", number=1, known=True):
    request = {"model": "deepseek-flash", "thinking": {"type": "disabled"},
               "temperature": 0, "max_tokens": 2048,
               "messages": [{"role": "user", "content": body}]}
    raw = json.dumps(request, ensure_ascii=False)
    record = {"id": number, "phase": phase, "question_id": qid, "request": request,
              "request_wire_utf8": raw, "request_sha256": digest(raw.encode()),
              "input_bytes": len(raw.encode()), "status": "COMPLETED" if known else "FAILED",
              "cost_status": "KNOWN" if known else "UNKNOWN", "elapsed_seconds": 0.5}
    if known:
        usage = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10,
                 "prompt_cache_hit_tokens": 2}
        response = {"usage": usage, "choices": [{"message": {"content": output}}],
                    "model": "synthetic-model", "system_fingerprint": "synthetic-fingerprint"}
        raw_response = json.dumps(response)
        record.update(usage=usage, response=response, response_wire_utf8=raw_response,
                      response_sha256=digest(raw_response.encode()))
    return record


def ledger(records):
    return {"records": records, "actual_attempts": len(records),
            "input_bytes": sum(r["input_bytes"] for r in records), "closed": True}


def common_resource_profile(root, *, unknown=False, missing=False):
    runtime = root / "runtime"
    runtime.mkdir()
    (runtime / "source.txt").write_text("α synthetic source", encoding="utf-8")
    text = (runtime / "source.txt").read_text(encoding="utf-8")
    schedule, statuses = [], []
    attempts = 0
    for arm in ("P0", "A", "S"):
        for q in range(6):
            for repeat in range(3):
                uid = f"{arm}-Q{q}-{repeat}"
                unit = {"unit_id": uid, "arm": arm, "question_id": f"Q{q}",
                        "repeat": repeat, "source_id": "source", "planned_max_attempts": 8}
                schedule.append(unit)
                result = {**unit, "status": "COMPLETED", "answer": "final", "elapsed_seconds": 1.5}
                if arm == "P0":
                    records = [wire_record(output="final")]
                    result.update(response={"answer": "final"}, trace={"native_generator_result": {"answer": "final"}})
                else:
                    chunk = {"chunk_id": "c1", "source_id": "source", "start": 0, "end": len(text)}
                    maps = [{"chunk_id": "c1", "map_call_id": 1, "output": "mapped"}]
                    body = f"[CHUNK c1; source source; Unicode [0,{len(text)})]\n{text}"
                    records = [wire_record(body, "mapped"),
                               wire_record("[MAP OUTPUTS]\n" + json.dumps(maps), "final", number=2)]
                    result.update(chunks=[chunk], maps=maps)
                if uid == "P0-Q0-0" and (unknown or missing):
                    result["status"] = "FAILED"
                    records = [wire_record(known=False)] if unknown else []
                path = root / "out/units" / uid
                save(path / "result.json", result)
                if not (missing and uid == "P0-Q0-0"):
                    save(path / "calls/ledger.json", ledger(records))
                attempts += len(records)
                statuses.append({"unit_id": uid})
    registration = {"runtime": str(runtime), "sources": {"source": {"file": "source.txt"}}, "schedule": schedule}
    save(root / "registration.json", registration)
    save(root / "registration.sha256.json", {"registration_sha256": digest((root / "registration.json").read_bytes())})
    save(root / "out/profile-status.json", {"status": "FINISHED", "units": statuses,
                                            "actual_attempts": attempts, "elapsed_seconds": 9})
    return root


@pytest.mark.parametrize("variant", ["completed", "unknown", "missing"])
def test_common_resource_reconciles_real_wire_map_reduce_and_unknown_cost(tmp_path, capsys, variant):
    from research.common_resource_audit import audit
    root = common_resource_profile(tmp_path, unknown=variant == "unknown", missing=variant == "missing")
    events = []
    result = audit(root, progress=events.append)
    assert capsys.readouterr().out == ""
    assert result["status"] == "WIRE_RESOURCE_AUDIT_PASS"
    assert result["registered_units"] == 54
    assert result["resources"]["A"]["attempts"] == 36
    assert result["resources"]["S"]["input_tokens"] == 252
    assert result["resources"]["P0"]["unknown_cost_requests"] == (variant == "unknown")
    assert result["resources"]["P0"]["attempts"] == (17 if variant == "missing" else 18)
    assert result["total_tokens"] == (900 if variant == "completed" else 890)
    assert result["response_models"] == ["synthetic-model"]
    assert result["provider_fingerprints"] == ["synthetic-fingerprint"]
    assert result["semantic_scoring"] == "NOT_ASSESSED"
    assert load(root / "resource-audit.json") == result
    assert events == [{"status": "WIRE_RESOURCE_AUDIT_PASS", "registered_units": 54,
                       "total_tokens": result["total_tokens"], "parent_elapsed_seconds": 9}]
    assert len(result["file_hashes"]) == (107 if variant == "missing" else 108)


@pytest.mark.parametrize("damage", ["registration", "wire", "map", "reduce", "usage", "identity", "active", "attempts"])
def test_common_resource_refuses_forged_or_incomplete_receipts(tmp_path, damage):
    from research.common_resource_audit import audit
    root = common_resource_profile(tmp_path)
    if damage == "registration":
        with (root / "registration.json").open("a") as handle:
            handle.write(" ")
    elif damage in {"active", "attempts"}:
        path = root / "out/profile-status.json"
        data = load(path)
        data["status" if damage == "active" else "actual_attempts"] = "RUNNING" if damage == "active" else 1
        save(path, data)
    elif damage == "identity":
        path = root / "out/units/A-Q0-0/result.json"
        data = load(path); data["question_id"] = "wrong"; save(path, data)
    elif damage == "map":
        path = root / "out/units/A-Q0-0/result.json"
        data = load(path); data["maps"][0]["output"] = "not mapped"; save(path, data)
    else:
        path = root / "out/units/A-Q0-0/calls/ledger.json"
        data = load(path)
        if damage == "wire":
            data["records"][0]["request_sha256"] = "0" * 64
        elif damage == "usage":
            data["records"][0]["usage"]["total_tokens"] += 1
        else:
            record = wire_record('[MAP OUTPUTS]\n[]', 'final', number=2)
            data["records"][1] = record
            data["input_bytes"] = sum(r["input_bytes"] for r in data["records"])
        save(path, data)
    with pytest.raises(AssertionError):
        audit(root)
    assert not (root / "resource-audit.json").exists()


def evaluation_profile(root):
    questions = [{"question_id": f"Q{q}", "items": [{"item_id": "I1", "atoms": [{"atom_id": "a1"}]}],
                  "qualifiers": [{"id": "q1"}]} for q in range(6)]
    answers, mapping, rows, evidence = [], [], [], []
    for arm in ("P0", "A", "S"):
        for q in range(6):
            for repeat in range(3):
                aid = f"{arm}-Q{q}-{repeat}"
                answers.append({"answer_id": aid, "question_id": f"Q{q}", "answer": "fact", "run_status": "COMPLETED"})
                mapping.append({"answer_id": aid, "unit_id": aid, "arm": arm, "repeat": repeat})
                rows.append({"answer_id": aid, "question_id": f"Q{q}", "items": [{"item_id": "I1", "present": True,
                             "atoms": [{"atom_id": "a1", "correct": True, "reason": "supported", "quote": "fact"}]}],
                             "qualifiers": [{"id": "q1", "correct": True}], "extra_items": [],
                             "predicted_item_count": 1, "completeness_claims": [{"text": "all facts"}]})
                evidence.append({"answer_id": aid, "claims": [{"content_correct": True, "in_scope": True,
                                 "input_supported": True, "citation_entails": True}], "claim_audit_complete": True,
                                 "extra_adjudications": [], "completeness_audit_complete": True,
                                 "completeness_claims": [{"content_claim_index": 0, "text": "all facts",
                                                          "status": ["SUPPORTED_COMPLETENESS"]}]})
    out = root / "evaluation"
    save(out / "content-packet.json", {"questions": questions, "answers": answers})
    save(out / "operator-only-mapping.json", mapping)
    save(out / "content-final.json", {"answers": rows})
    save(out / "evidence-final.json", {"answers": evidence})
    return out


def test_evaluation_distinguishes_required_extra_metadata_and_unknown_evidence(tmp_path, capsys):
    from research.common_evaluate_summary import summarize
    out = evaluation_profile(tmp_path)
    content, evidence, packet = (load(out / name) for name in ("content-final.json", "evidence-final.json", "content-packet.json"))
    content["answers"][0]["extra_items"] = [{"reason": "blind uncertain", "correct": None, "in_scope": None}]
    evidence["answers"][0]["extra_adjudications"] = [{"extra_index": 0, "reason": "source refutes",
        "correct": False, "in_scope": True, "source_locators": ["synthetic:1"]}]
    content["answers"][1]["items"][0]["atoms"][0]["correct"] = None
    evidence["answers"][1]["claims"][0]["input_supported"] = None
    evidence["answers"][2]["metadata_claims"] = [{"content_correct": False, "in_scope": None,
                                                   "input_supported": False, "citation_entails": None}]
    packet["answers"][3]["run_status"] = "FAILED"
    content["answers"][4]["predicted_item_count"] = None
    evidence["answers"][5]["completeness_claims"][0]["status"] = ["UNSUPPORTED_COMPLETENESS"]
    for name, data in (("content-final.json", content), ("evidence-final.json", evidence), ("content-packet.json", packet)):
        save(out / name, data)
    frozen = (out / "content-final.json").read_bytes()
    events = []
    result = summarize(tmp_path, progress=events.append)
    assert capsys.readouterr().out == ""
    by_id = {r["answer_id"]: r for r in result["units"]}
    first = by_id["P0-Q0-0"]
    assert first["required_content_complete"] is True and first["content_complete"] is False
    extra = first["source_adjudicated_extra_items"][0]
    assert extra["blind_content_reason"] == "blind uncertain" and extra["reason"] == "source refutes"
    assert extra["correct"] is False and extra["source_locators"] == ["synthetic:1"]
    assert by_id["P0-Q0-1"]["atoms_unknown"] == 1
    assert by_id["P0-Q0-1"]["unknown_support_rate"] == 1
    assert by_id["P0-Q0-2"]["metadata_content_false"] == 1
    assert by_id["P0-Q0-2"]["metadata_unknown"] == 1
    assert by_id["P0-Q1-0"]["item_recall"] is None
    assert by_id["P0-Q1-0"]["strict_supported_complete"] is False
    assert by_id["P0-Q1-1"]["item_precision"] is None
    assert by_id["P0-Q1-2"]["strict_supported_complete"] is False
    assert len(result["question_arm_groups"]) == 18
    assert events[0]["strict_successes_by_arm"] == {"P0": 13, "A": 18, "S": 18}
    assert result["scientific_stage"] == "M2_OPEN" and result["inferential_tests"] == []
    assert result["human_gold_verified"] is False
    assert (out / "content-final.json").read_bytes() == frozen
    assert load(out / "quality-summary.json") == result
    assert result["input_hashes"]["content-final.json"] == digest(frozen)


@pytest.mark.parametrize("damage", ["evidence_missing", "incomplete_audit", "missing_promise", "wrong_text", "duplicate_extra", "invalid_boolean", "prediction", "missing_file"])
def test_evaluation_refuses_missing_or_malformed_adjudication(tmp_path, damage):
    from research.common_evaluate_summary import summarize
    out = evaluation_profile(tmp_path)
    content = load(out / "content-final.json")
    evidence = load(out / "evidence-final.json")
    if damage == "evidence_missing": evidence["answers"].pop()
    elif damage == "incomplete_audit": evidence["answers"][0]["claim_audit_complete"] = False
    elif damage == "missing_promise": evidence["answers"][0]["completeness_claims"] = []
    elif damage == "wrong_text": evidence["answers"][0]["completeness_claims"][0]["text"] = "forged"
    elif damage == "duplicate_extra":
        content["answers"][0]["extra_items"] = [{}, {}]
        evidence["answers"][0]["extra_adjudications"] = [{"extra_index": 0}, {"extra_index": 0}]
    elif damage == "invalid_boolean": evidence["answers"][0]["claims"][0]["input_supported"] = "yes"
    elif damage == "prediction": content["answers"][0]["predicted_item_count"] = 0
    save(out / "content-final.json", content)
    save(out / "evidence-final.json", evidence)
    if damage == "missing_file": (out / "evidence-final.json").unlink()
    with pytest.raises(FileNotFoundError if damage == "missing_file" else AssertionError):
        summarize(tmp_path)
    assert not (out / "quality-summary.json").exists()


def development_profile(root, *, unknown=False, omit_outputs=False):
    out, run, data = root / "reports", root / "snapshot", root / "data"
    run.mkdir(); data.mkdir()
    source = data / "source.txt"; source.write_text("source body", encoding="utf-8")
    code = run / "synthetic.py"; code.write_text("VALUE = 1\n", encoding="utf-8")
    save(run / "snapshot.json", {"files": {"synthetic.py": digest(code.read_bytes())}})
    save(data / "sources.json", [{"source_id": "s1", "canonical_file": "source.txt"}])
    chunks = [{"start": 0, "end": 11, "chunk_id": "c1"}]
    work = [{"question_id": "Q1", "source_id": "s1", "chunks": chunks},
            {"question_id": "Q2", "source_id": "s1", "chunks": []}]
    save(out / "inputs.json", {"work": work, "data_dir": str(data), "input_hashes": {str(source): digest(source.read_bytes())}})
    save(out / "registration.json", {"source_snapshot_sha256": digest((run / "snapshot.json").read_bytes()),
                                     "inputs_sha256": digest((out / "inputs.json").read_bytes())})
    maps = [{"chunk_id": "c1", "output": "mapped"}]
    records = [wire_record("prefix source body", "mapped"), wire_record("[MAP OUTPUTS]\n" + json.dumps(maps), "answer", number=2),
               wire_record(phase="index", number=3, known=not unknown)]
    records[1]["request"].pop("temperature")
    records[1]["request_wire_utf8"] = json.dumps(records[1]["request"])
    records[1]["request_sha256"] = digest(records[1]["request_wire_utf8"].encode())
    records[1]["input_bytes"] = len(records[1]["request_wire_utf8"].encode())
    save(out / "calls/ledger.json", ledger(records))
    save(out / "execution-status.json", {"elapsed_seconds": 12, "all_steps_completed": not unknown})
    if not omit_outputs:
        save(out / "Q1.a.json", {"maps": maps, "answer": "answer"})
        save(run / "artifacts/Q1.p0.json", {"document_id": "s1", "response": {"answer": "a" * 4000},
                                            "trace": {"native_generator_result": {"answer": "a" * 4100}}})
        save(run / "artifacts/Q2.p0.json", {"document_id": "s1", "response": {"answer": "abstain"}, "trace": {}})
        save(run / "artifacts/index-result.json", {"documents": 1})
    return out, run, source, code


@pytest.mark.parametrize("variant", ["complete", "unknown", "missing_outputs", "changed_sources", "changed_code"])
def test_development_summary_checks_reconciliation_and_honest_unverified_boundaries(tmp_path, capsys, variant):
    from research.development_summarize import summarize
    out, run, source, code = development_profile(tmp_path, unknown=variant == "unknown", omit_outputs=variant == "missing_outputs")
    if variant == "changed_sources": source.write_text("source body\nchanged outside the selected slice", encoding="utf-8")
    if variant == "changed_code": code.write_text("VALUE = 2\n", encoding="utf-8")
    events = []
    summarize(out, run, progress=events.append)
    assert capsys.readouterr().out == ""
    report = load(out / "resource-summary.json")
    assert report["total"]["attempts"] == 3
    assert report["total"]["known_usage"]["total_tokens"] == (20 if variant == "unknown" else 30)
    assert report["total"]["unknown_cost_attempts"] == (variant == "unknown")
    assert report["wire_temperature_by_phase"]["a"] == {"omitted_calls": 1, "explicit_values": [0]}
    assert report["source_inputs_unchanged"] == (variant != "changed_sources")
    assert report["code_unchanged"] == (variant != "changed_code")
    assert report["same_weight_snapshot_verified"] is False
    assert report["semantic_scoring"] == "NOT_EXECUTED" and report["scientific_stage"] == "M2_OPEN"
    if variant == "missing_outputs":
        assert report["A_input_chain_checks"] == report["P0_native_route_checks"] == []
        assert report["index_result"] is None
    else:
        assert report["A_input_chain_checks"][0]["map_to_reduce_complete"] is True
        assert [r["api_4000_limit_verified"] for r in report["P0_native_route_checks"]] == [True, False]
    assert events[0]["total"] == report["total"]


@pytest.mark.parametrize("damage", ["snapshot", "inputs", "wire", "response", "map", "p0"])
def test_development_summary_refuses_tampered_hashes_and_broken_generation_chain(tmp_path, damage):
    from research.development_summarize import summarize
    out, run, _, _ = development_profile(tmp_path)
    if damage in {"snapshot", "inputs"}:
        path = run / "snapshot.json" if damage == "snapshot" else out / "inputs.json"
        with path.open("a") as handle: handle.write(" ")
    elif damage in {"wire", "response"}:
        path = out / "calls/ledger.json"; state = load(path)
        state["records"][0]["request_sha256" if damage == "wire" else "response_sha256"] = "f" * 64
        save(path, state)
    elif damage == "map":
        path = out / "Q1.a.json"; data = load(path); data["maps"][0]["output"] = "forged"; save(path, data)
    else:
        path = run / "artifacts/Q1.p0.json"; data = load(path); data["response"]["answer"] = "forged"; save(path, data)
    with pytest.raises(AssertionError): summarize(out, run)
    assert not (out / "resource-summary.json").exists()


def test_development_prepare_real_html_scope_and_unresolved_question(tmp_path, capsys):
    from research.development_profile_cli import prepare_inputs
    data = tmp_path / "data"; data.mkdir()
    text = "1 Intro\nsource body\n2 End\ntail"
    canonical = data / "canonical.txt"; canonical.write_text(text, encoding="utf-8")
    raw = data / "source.html"
    raw.write_text("<html><body><h1>1 Intro</h1><p>source body</p><h1>2 End</h1><p>tail</p></body></html>", encoding="utf-8")
    blocks = []
    for tag, n, a, b in (("h1", 1, 0, 7), ("p", 1, 8, 19), ("h1", 2, 20, 25), ("p", 2, 26, 30)):
        blocks.append({"tag": tag, "xpath": f"/html[1]/body[1]/{tag}[{n}]", "start": a, "end": b, "text": text[a:b]})
    save(data / "blocks.json", {"blocks": blocks})
    save(data / "sources.json", [{"source_id": "s1", "canonical_file": "canonical.txt", "raw_file": "source.html",
        "canonical_sha256": digest(canonical.read_bytes()), "source_sha256": digest(raw.read_bytes()), "section_or_page_map": "blocks.json"}])
    save(data / "questions.input.json", [{"question_id": f"Q{i}", "source_id": "s1", "question": "section 1" if i < 5 else "unspecified",
                                          "range_condition": "explicit"} for i in range(6)])
    save(tmp_path / "previous.json", {"units": [{"messages": [{"content": "system"}]}], "map_instruction": "map", "reduce_instruction": "reduce"})
    xml = tmp_path / "unused.xml"; xml.write_text("<pdf2xml/>", encoding="utf-8")
    out = tmp_path / "out"; events = []
    prepare_inputs(data, xml, out, tmp_path / "previous.json", progress=events.append)
    assert capsys.readouterr().out == ""
    report = load(out / "inputs.json")
    assert report["A_planned_calls"] == 10
    assert report["work"][0]["assembly"]["status"] == "COMPLETE_SCOPE"
    assert report["work"][0]["chunks"] == [{"source_id": "s1", "start": 0, "end": 20, "chunk_id": "s1-A-0-20"}]
    assert report["work"][5]["planned_calls"] == 0
    assert report["gold_loaded"] is False and report["semantic_scoring"] == "NOT_EXECUTED"
    assert report["input_hashes"][str(canonical.resolve())] == digest(canonical.read_bytes())
    assert events[0]["A_planned_calls"] == 10
    canonical.write_text("tampered", encoding="utf-8")
    with pytest.raises(AssertionError): prepare_inputs(data, xml, tmp_path / "rejected", tmp_path / "previous.json")
    assert not (tmp_path / "rejected/inputs.json").exists()


@pytest.mark.parametrize("mode", ["complete", "failure", "timeout", "expired"])
def test_authorized_supervisor_sanitizes_child_boundary_and_stops_on_failure(tmp_path, monkeypatch, capsys, mode):
    """Exercise orchestration, never the paid child: only synthetic explicit env path is readable."""
    import subprocess
    import sys
    from types import SimpleNamespace
    import dotenv
    from research import development_run_authorized as supervisor

    repo = tmp_path / "synthetic-repo"
    run, out = repo / ".tmp/run", repo / "docs/review/run"
    save(run / "snapshot.json", {"files": {}})
    save(out / "inputs.json", {"gold_loaded": False, "model_requested": "deepseek-flash", "A_planned_calls": 14,
         "data_dir": str(repo / "data"), "xml": str(repo / "fixture.xml"),
         "work": [{"question_id": f"Q{i}", "source_id": "s1", "question": "synthetic question"} for i in range(6)]})
    env_path = repo / "backend/.env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("LANGEXTRACT_API_KEY=synthetic-not-a-provider-key\nLANGEXTRACT_MODEL_ID=deepseek-flash\nLANGEXTRACT_BASE_URL=https://api.deepseek.com\n", encoding="utf-8")
    real_values = dotenv.dotenv_values
    reads = []
    def checked_values(path):
        assert Path(path).resolve() == env_path.resolve()
        assert env_path.is_relative_to(tmp_path)
        reads.append(path)
        return real_values(path)
    monkeypatch.setattr(dotenv, "dotenv_values", checked_values)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    monkeypatch.setenv("UNRELATED_PROVIDER_KEY", "must-not-be-inherited")
    calls = []
    def controlled_child(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["cwd"] == run.resolve()
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
        assert "UNRELATED_PROVIDER_KEY" not in kwargs["env"]
        assert kwargs["stdout"] is subprocess.PIPE and kwargs["stderr"] is subprocess.PIPE
        assert kwargs["check"] is False
        if mode == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        output = (b'raw library log must disappear\n{"status":"COMPLETED","actual_attempts":1}\n'
                  b'{"status":"synthetic-not-a-provider-key"}\n'
                  b'{"status":"COMPLETED","unexpected":"must disappear"}\n[]\n')
        return SimpleNamespace(returncode=1 if mode == "failure" else 0, stdout=output, stderr=b"private upstream detail")
    monkeypatch.setattr(subprocess, "run", controlled_child)
    if mode == "expired":
        times = iter([0, 1801, 1802])
        monkeypatch.setattr(supervisor.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(sys, "argv", ["supervisor", "--repo-root", str(repo), "--run-root", str(run),
                                      "--artifacts", str(out), "--python", "synthetic-python-never-executed"])
    supervisor.main()
    report = load(out / "execution-status.json")
    text = (out / "execution-status.json").read_text(encoding="utf-8")
    assert len(reads) == 1
    assert "private upstream" not in text and "raw library" not in text and "synthetic-not-a-provider-key" not in text
    assert report["scientific_stage"] == "M2_OPEN" and report["semantic_scoring"] == "NOT_EXECUTED"
    if mode == "complete":
        assert len(calls) == 8 and report["all_steps_completed"] is True
        assert [r["step"] for r in report["steps"]] == ["index", *[f"Q{i}-p0" for i in range(6)], "A-all"]
        assert all(r["safe_child_status"] == [{"status": "COMPLETED", "actual_attempts": 1}] for r in report["steps"])
        assert all(r["upstream_logs_omitted"] is True for r in report["steps"])
    else:
        assert report["all_steps_completed"] is False and len(report["steps"]) == 1
        expected = {"failure": "FAILED", "timeout": "LOCAL_DEADLINE_REMOTE_COST_UNKNOWN", "expired": "LOCAL_WINDOW_NOT_STARTED"}[mode]
        assert report["steps"][0]["status"] == expected
        assert len(calls) == (0 if mode == "expired" else 1)
    emitted = capsys.readouterr().out
    assert "raw library" not in emitted and "private upstream" not in emitted
    assert "synthetic-not-a-provider-key" not in emitted
