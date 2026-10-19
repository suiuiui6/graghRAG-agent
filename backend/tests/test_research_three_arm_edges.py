"""Synthetic registered research boundaries; no historical data or remote requests."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("No network in registered research fixture tests")
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_fixture(root):
    """An intentionally minimal AST call graph, never imported or executed."""
    frozen, data = root / "frozen", root / "public"
    graph = {
        "generator.py": "class GenerationConfig:\n max_retries: int = 1\ndef _post_with_bounded_retries(config):\n attempts=max(0, int(config.max_retries)) + 1\n return post()\ndef generate_answer():\n return _post_with_bounded_retries()\ndef generate():\n return generate_answer()\n",
        "retrieval.py": "def preprocess_query():\n return post()\nclass RetrievalPipeline:\n def __init__(self,query_optimizer=None,domain_dict=None):\n  pass\n def retrieve(self):\n  return self._retrieve_impl()\n def _retrieve_impl(self):\n  return preprocess_query()\n",
        "routes/rag_query.py": "def _generate_scoped_rag():\n config=GenerationConfig()\n pipeline=RetrievalPipeline()\n return pipeline.generate()\n",
        "config.py": "DEFAULT_ENABLE_GLOBAL_MODE=False\n",
        "models.py": "class QueryOptions:\n enable_global_mode: bool = Field(default=DEFAULT_ENABLE_GLOBAL_MODE)\n",
        "research/development_isolation.py": "def query_source():\n return QueryOptions()\n",
    }
    files = {}
    for name, source in graph.items():
        path = frozen / "backend" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        files["backend/" + name] = sha(path)
    save(frozen / "snapshot.json", {"files": files})
    save(frozen / "backend/output/docs_store.json", [{"document_id": sid} for sid in ("LCNC-HOME", "NIST-8091")])
    records, hashes = [], {}
    for sid, size in (("LCNC-HOME", 16001), ("NIST-8091", 24001)):
        path = data / (sid + ".txt"); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * size, encoding="utf-8")
        records.append({"source_id": sid, "canonical_file": path.name, "canonical_sha256": sha(path)})
        hashes[str(path)] = sha(path)
    save(data / "sources.json", records)
    save(data / "questions.input.json", [{"question_id": f"Q{i}"} for i in range(6)])
    work = [{"question_id": f"Q{i}", "source_id": "LCNC-HOME" if i < 3 else "NIST-8091",
             "question": "section 1", "chunks": [{"chunk_id": f"q{i}-c{j}"} for j in range(2 if i < 2 else 1)],
             "resolution": {}} for i in range(6)]
    inputs = root / "inputs.json"
    save(inputs, {"input_hashes": hashes, "data_dir": str(data), "questions_sha256": sha(data / "questions.input.json"),
                  "work": work, "system_prompt": "synthetic system", "map_instruction": "map", "reduce_instruction": "reduce", "sources": {}})
    return frozen, inputs


def registered_fixture(root):
    from research.common_three_arm import prepare
    frozen, inputs = frozen_fixture(root)
    profile = root / "profile"
    reg = prepare(frozen, inputs, profile)
    return profile, reg


def test_prepare_real_ast_proof_and_locked_registration_are_self_consistent(tmp_path):
    from research.common_three_arm import verify_registration
    profile, reg = registered_fixture(tmp_path)
    assert reg["status"] == "REGISTERED_NOT_EXECUTED" and reg["gold_loaded"] is False
    assert reg["path_proof"]["per_unit_max_attempts"] == 3
    assert len(reg["schedule"]) == 54 and reg["global_path_attempts"] == 177
    assert (reg["A_calls_per_round"], reg["S_calls_per_round"]) == (14, 27)
    assert reg["model_config"]["temperature"] == 0
    assert verify_registration(profile) == reg
    runtime = Path(reg["runtime"])
    docs = load(runtime / "backend/output/docs_store.json")
    assert all(Path(d["kg_path"]).is_relative_to(runtime) for d in docs)
    assert reg["frozen_runtime"] != reg["runtime"]
    assert reg["environment"]["requests"]


@pytest.mark.parametrize("fault", ["overlap", "source", "question", "work", "documents", "canonical", "calls"])
def test_prepare_rejects_unapproved_source_identity_or_budget(tmp_path, fault):
    from research.common_three_arm import prepare
    frozen, inputs = frozen_fixture(tmp_path)
    data = load(inputs); profile = tmp_path / "profile"
    if fault == "overlap": profile = frozen / "child"
    elif fault == "source": Path(next(iter(data["input_hashes"]))).write_text("changed", encoding="utf-8")
    elif fault == "question": (Path(data["data_dir"]) / "questions.input.json").write_text("[] ", encoding="utf-8")
    elif fault == "work": data["work"].pop(); save(inputs, data)
    elif fault == "documents": save(frozen / "backend/output/docs_store.json", [{"document_id": "unexpected"}])
    elif fault == "canonical":
        path = Path(data["data_dir"]) / "sources.json"; records = load(path); records[0]["canonical_sha256"] = "0" * 64; save(path, records)
    else: data["work"][0]["chunks"] = []; save(inputs, data)
    with pytest.raises(ValueError): prepare(frozen, inputs, profile)
    assert not (profile / "registration.json").exists()


@pytest.mark.parametrize("fault", ["registration", "code", "kg", "source", "snapshot", "environment", "governance"])
def test_registered_inputs_fail_closed_after_hash_or_environment_drift(tmp_path, fault):
    from research import common_three_arm as runner
    profile, reg = registered_fixture(tmp_path)
    runtime = Path(reg["runtime"])
    if fault == "registration":
        with (profile / "registration.json").open("a") as handle: handle.write(" ")
    elif fault == "code": (runtime / "backend/generator.py").write_text("changed", encoding="utf-8")
    elif fault == "kg": (runtime / "backend/output/docs_store.json").write_text("[]", encoding="utf-8")
    elif fault == "source": (runtime / reg["sources"]["LCNC-HOME"]["file"]).write_text("changed", encoding="utf-8")
    elif fault == "snapshot": (runtime / "snapshot.json").write_text("{}", encoding="utf-8")
    else:
        if fault == "environment": reg["environment"] = {}
        else:
            document = tmp_path / "synthetic-contract.txt"; document.write_text("old", encoding="utf-8")
            reg["governance_sha256"] = {str(document): sha(document)}
            document.write_text("changed", encoding="utf-8")
        save(profile / "registration.json", reg)
        save(profile / "registration.sha256.json", {"registration_sha256": sha(profile / "registration.json")})
    with pytest.raises(ValueError): runner.verify_registration(profile)


def test_clear_cache_rejects_directory_without_touching_contents(tmp_path):
    from research.common_three_arm import clear_unit_cache
    cache = tmp_path / "runtime/backend/output/rewrite-cache.sqlite3"
    cache.mkdir(parents=True); sentinel = cache / "keep.txt"; sentinel.write_text("unchanged")
    with pytest.raises(ValueError, match="缓存清理路径不是文件"):
        clear_unit_cache(tmp_path, {"runtime": str(tmp_path / "runtime")})
    assert sentinel.read_text() == "unchanged"


@pytest.mark.parametrize("mode", ["missing", "nonzero", "timeout_partial", "unknown", "corrupt", "overspend", "remaining"])
def test_supervisor_real_registration_local_boundary_and_stop_rules(tmp_path, monkeypatch, mode):
    from research import common_three_arm as runner
    import dotenv
    profile, reg = registered_fixture(tmp_path)
    env_path = tmp_path / "synthetic.env"; env_path.write_text("LANGEXTRACT_API_KEY=synthetic-offline\n", encoding="utf-8")
    real_values = dotenv.dotenv_values
    def checked_values(path):
        assert Path(path).resolve() == env_path.resolve()
        return real_values(path)
    monkeypatch.setattr(dotenv, "dotenv_values", checked_values)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    calls = []
    def child(command, **kwargs):
        uid = command[command.index("--unit-id") + 1]
        unit = next(u for u in reg["schedule"] if u["unit_id"] == uid)
        calls.append(uid)
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        path = profile / "out/units" / uid
        if mode == "timeout_partial":
            save(path / "calls/ledger.json", {"actual_attempts": 1, "records": [{"status": "SENT_PENDING", "cost_status": "UNKNOWN"}]})
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if mode != "missing": save(path / "result.json", {**unit, "status": "COMPLETED", "answer": "synthetic", "actual_attempts": 176 if mode == "remaining" else 1})
        if mode == "corrupt":
            ledger = path / "calls/ledger.json"; ledger.parent.mkdir(); ledger.write_text("broken-json", encoding="utf-8")
        elif mode in {"unknown", "overspend"}:
            save(path / "calls/ledger.json", {"actual_attempts": 178 if mode == "overspend" else 1,
                 "records": [{"status": "COMPLETED", "cost_status": "UNKNOWN" if mode == "unknown" else "KNOWN",
                              "usage": {"prompt_tokens": 7, "completion_tokens": 3}}]})
        return subprocess.CompletedProcess(command, 1 if mode == "nonzero" else 0, stdout="untrusted body", stderr="untrusted diagnostic")
    monkeypatch.setattr(subprocess, "run", child)
    result = runner.supervise(profile, env_path)
    assert result["status"] == "STOPPED" and len(result["units"]) == 54
    assert len(calls) == 1 and all(r["status"] == "NOT_RUN" for r in result["units"][2:])
    if mode == "remaining":
        assert result["units"][0]["status"] == "COMPLETED"
        assert "剩余额度不足" in result["units"][1]["stop_reason"]
    else: assert result["units"][0]["status"] == "PROFILE_STOP"
    if mode == "timeout_partial": assert result["units"][0]["partial_ledger_sha256"]
    if mode == "corrupt": assert result["units"][0]["stop_reason"] == "预算账本损坏"
    if mode == "overspend": assert result["units"][0]["stop_reason"] == "全组路径请求上限超额"
    if mode != "timeout_partial":
        receipt = load(profile / "out/process" / (calls[0] + ".json"))
        assert receipt["raw_output_omitted"] is True and set(receipt) == {"exit_code", "stdout_sha256", "stderr_sha256", "raw_output_omitted"}
    with pytest.raises(ValueError, match="不自动续跑"):
        runner.supervise(profile, env_path)


def test_supervisor_missing_credential_fails_before_child(tmp_path, monkeypatch):
    from research import common_three_arm as runner
    import dotenv
    profile, _ = registered_fixture(tmp_path)
    env_path = tmp_path / "synthetic-empty.env"; env_path.write_text("# no credential\n", encoding="utf-8")
    real_values = dotenv.dotenv_values
    def checked(path):
        assert Path(path) == env_path
        return real_values(path)
    monkeypatch.setattr(dotenv, "dotenv_values", checked)
    with pytest.raises(ValueError, match="缺少环境文件密钥"): runner.supervise(profile, env_path)
    assert not (profile / "out").exists()


def packet_fixture(root):
    from research.common_evaluation_packets import prepare
    schedule = []
    questions = []
    for q in range(6):
        items = [{"item": f"item-{i}", "scoring_atoms": [{"atom_id": f"a{a}", "expected": "fact", "evidence": [{"quote": "fact"}]} for a in range(3 if q * 6 + i < 9 else 2)]} for i in range(6)]
        questions.append({"question_id": f"Q{q}", "question": "synthetic?", "gold_items": items,
                          "required_answer_qualifiers": [{"claim": "only synthetic"}]})
        for arm in ("P0", "A", "S"):
            for repeat in range(3):
                uid = f"Q{q}-{arm}-{repeat}"; unit = {"unit_id": uid, "question_id": f"Q{q}", "arm": arm, "repeat": repeat}
                schedule.append(unit)
                save(root / "out/units" / uid / "result.json", {**unit, "status": "COMPLETED", "answer": "fact"})
    save(root / "registration.json", {"schedule": schedule})
    save(root / "out/profile-status.json", {"status": "FINISHED"})
    gold = root / "synthetic-gold.json"; save(gold, {"questions": questions})
    prepare(root, gold)
    return gold, schedule


@pytest.mark.parametrize("mode", ["absent_terminal", "active", "missing_unit", "pending_unit", "reuse"])
def test_packet_publication_requires_terminated_complete_and_fresh_profile(tmp_path, mode):
    from research.common_evaluation_packets import prepare
    gold, schedule = packet_fixture(tmp_path)
    if mode == "reuse":
        before = (tmp_path / "evaluation/content-packet.json").read_bytes()
    else:
        # Use a fresh sibling for the rejection. Existing frozen packet stays untouched.
        fresh = tmp_path / "fresh"; fresh.mkdir()
        save(fresh / "registration.json", {"schedule": schedule})
        if mode != "absent_terminal": save(fresh / "out/profile-status.json", {"status": "RUNNING" if mode == "active" else "FINISHED"})
        if mode == "pending_unit":
            for i, unit in enumerate(schedule): save(fresh / "out/units" / unit["unit_id"] / "result.json", {**unit, "status": "PENDING" if i == 0 else "COMPLETED"})
        with pytest.raises(ValueError): prepare(fresh, gold)
        assert not (fresh / "evaluation").exists()
        return
    with pytest.raises(ValueError, match="overwrite"): prepare(tmp_path, gold)
    assert (tmp_path / "evaluation/content-packet.json").read_bytes() == before


def test_evidence_reveal_verifies_two_locked_reviews_and_exact_wire(tmp_path):
    from research.common_evaluation_packets import prepare_evidence, validate_judgments
    packet_fixture(tmp_path)
    out = tmp_path / "evaluation"; packet = load(out / "content-packet.json")
    rows = []
    for answer in packet["answers"]:
        q = next(q for q in packet["questions"] if q["question_id"] == answer["question_id"])
        rows.append({"answer_id": answer["answer_id"], "question_id": q["question_id"],
                     "items": [{"item_id": item["item_id"], "present": True,
                                "atoms": [{"atom_id": a["atom_id"], "correct": True, "reason": "synthetic", "quote": "fact"} for a in item["atoms"]]} for item in q["items"]],
                     "qualifiers": [{"id": "Q01"}], "extra_items": [], "completeness_claims": []})
    reviewers = []
    for name in ("one.json", "two.json"):
        save(out / name, {"answers": rows}); reviewers.append({"file": name, "sha256": sha(out / name)})
    save(out / "content-lock.json", {"reviewers": reviewers})
    mapping = load(out / "operator-only-mapping.json")
    uid = mapping[0]["unit_id"]
    request = {"messages": [{"role": "user", "content": "synthetic source"}]}
    raw = json.dumps(request)
    save(tmp_path / "out/units" / uid / "calls/ledger.json", {"records": [{"status": "NOT_SENT"},
        {"id": 1, "status": "COMPLETED", "request_wire_utf8": raw, "request_sha256": hashlib.sha256(raw.encode()).hexdigest(),
         "request": request, "response": {"choices": [{"message": {"content": "fact"}}]}, "response_sha256": "synthetic-response-digest"},
        {"id": 2, "status": "FAILED", "request_wire_utf8": raw, "request_sha256": hashlib.sha256(raw.encode()).hexdigest(), "request": request}]})
    events = []; prepare_evidence(tmp_path, progress=events.append)
    packs = [load(out / f'evidence-Q{i}.json') for i in range(6)]
    assert events == [{"status": "EVIDENCE_PACKS_PREPARED", "questions": 6}]
    assert all(len(pack["units"]) == 9 for pack in packs)
    unit = next(u for pack in packs for u in pack["units"] if u["unit_id"] == uid)
    assert [call["output"] for call in unit["calls"]] == ["fact", None]
    assert [call["status"] for call in unit["calls"]] == ["COMPLETED", "FAILED"]
    assert packs[0]["mode"] == "REVEALED_INPUT_SUPPORT_AUDIT_AFTER_CONTENT_LOCK"
    assert validate_judgments(out / "content-packet.json", out / "one.json")["semantic_correctness"] == "REQUIRES_INDEPENDENT_REVIEW"
    locked = (out / "one.json").read_bytes()
    save(out / "one.json", {"answers": []})
    with pytest.raises(AssertionError): prepare_evidence(tmp_path)
    (out / "one.json").write_bytes(locked)
    ledger_path = tmp_path / "out/units" / uid / "calls/ledger.json"
    state = load(ledger_path); state["records"][1]["request_sha256"] = "bad"; save(ledger_path, state)
    with pytest.raises(AssertionError): prepare_evidence(tmp_path)


def test_scope_intervals_merge_only_adjacent_and_keep_p0_unassessable(tmp_path):
    from research.common_scope_audit import audit, bindings
    work = [{"question_id": "DEV-L01", "source_id": "s", "chunks": [{"start": 2, "end": 5}, {"start": 5, "end": 8}]}]
    save(tmp_path / "registration.json", {"work": work, "sources": {"s": {"chunks": [{"start": 0, "end": 5}, {"start": 5, "end": 8}, {"start": 9, "end": 11}]}}})
    save(tmp_path / "out/profile-status.json", {"status": "FINISHED"})
    gold = tmp_path / "synthetic-gold.json"
    save(gold, {"questions": [{"question_id": "DEV-L01", "scope": {"canonical_char_half_open": [2, 8]},
                              "facts": [{"evidence": {"canonical_char_half_open": [3, 4]}}, "plain scalar"]}]})
    assert bindings({"a": [{"canonical_char_half_open": [1, 2]}, 3], "b": None}) == [[1, 2]]
    result = audit(tmp_path, gold)
    a, s, p0 = result["rows"]
    assert a["body_visited_intervals"] == [[2, 8]] and a["target_region_access_precision"] == 1
    assert s["body_visited_intervals"] == [[0, 8], [9, 11]] and s["target_region_access_precision"] == 0.6
    assert s["selected_scope_verdict"] == "UNASSESSABLE" and s["gold_bound_regions_fully_visited"] == 2
    assert p0["body_visited_intervals"] is None and p0["target_region_access_recall"] is None
    assert result["total_gold_bound_regions_per_round"] == 2
    work[0]["chunks"] = [{"start": 3, "end": 8}]
    save(tmp_path / "registration.json", {"work": work, "sources": {"s": {"chunks": []}}})
    with pytest.raises(AssertionError): audit(tmp_path, gold)


def test_protection_exports_hashes_only_and_cli_detects_changed_assets(tmp_path, monkeypatch, capsys):
    from research import common_protection as protection
    repo = tmp_path / "synthetic-repo"
    secret_name = repo / "backend/output/kg/private-name/body.txt"
    secret_name.parent.mkdir(parents=True); secret_name.write_bytes(b"private synthetic body")
    docs = repo / "backend/output/docs_store.json"; docs.write_text("[]", encoding="utf-8")
    before = protection.snapshot(repo)
    expected_name = hashlib.sha256(b"backend/output/kg/private-name/body.txt").hexdigest()
    assert before["file_count"] == 2 and before["bytes"] == 24
    assert before["files"][expected_name]["sha256"] == sha(secret_name)
    assert "private-name" not in json.dumps(before) and "private synthetic body" not in json.dumps(before)
    baseline = tmp_path / "baseline.json"; save(baseline, before)
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["protection", "--repo", str(repo), "--output", str(output)])
    runpy.run_path(protection.__file__, run_name="__main__")
    assert "unchanged" not in load(output)
    monkeypatch.setattr(sys, "argv", ["protection", "--repo", str(repo), "--output", str(output), "--compare", str(baseline)])
    runpy.run_path(protection.__file__, run_name="__main__")
    assert load(output)["unchanged"] is True
    secret_name.write_bytes(b"changed")
    with pytest.raises(SystemExit) as exc: runpy.run_path(protection.__file__, run_name="__main__")
    assert exc.value.code == 1 and load(output)["unchanged"] is False
    assert "private-name" not in capsys.readouterr().out
