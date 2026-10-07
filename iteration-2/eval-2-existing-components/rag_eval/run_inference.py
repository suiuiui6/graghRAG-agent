"""
RAG eval inference runner.

This harness exercises the production GraphRAG endpoint directly at
`POST /api/v1/rag/query` via FastAPI's in-process TestClient, so the raw runs
reflect the same request/response contract used by the primary backend path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

CURRENT_DIR = Path(__file__).resolve().parent
CURRENT_DIR_STR = str(CURRENT_DIR)
if CURRENT_DIR_STR not in sys.path:
    sys.path.insert(0, CURRENT_DIR_STR)

from run_inference_helpers import (
    extract_node_ids_from_text,
    extract_retrieved_node_ids_from_rag_sources,
    normalize_token_usage,
)

ROOT = Path(r"D:/graghRAG-agent")
BACKEND_DIR = ROOT / "backend"
EVAL_DIR = ROOT / "iteration-2" / "eval-2-existing-components" / "rag_eval"
GT_PATH = EVAL_DIR / "ground_truth.json"
OUT_PATH = EVAL_DIR / "raw_runs.jsonl"
LOG_PATH = EVAL_DIR / "run.log"


def _parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run production GraphRAG eval inference.")
    parser.add_argument("--qids", nargs="*", default=None, help="Specific qids to run, e.g. Q01 Q03 Q47")
    parser.add_argument("--offset", type=int, default=int(os.environ.get("RAG_EVAL_OFFSET", "0")))
    parser.add_argument("--limit", type=int, default=None if os.environ.get("RAG_EVAL_LIMIT") in (None, "") else int(os.environ["RAG_EVAL_LIMIT"]))
    parser.add_argument("--append", action="store_true", default=_parse_bool_env("RAG_EVAL_APPEND"))
    parser.add_argument("--skip-existing", action="store_true", default=_parse_bool_env("RAG_EVAL_SKIP_EXISTING"))
    parser.add_argument("--out-path", default=os.environ.get("RAG_EVAL_OUT_PATH"), help="Optional custom raw_runs output path")
    parser.add_argument("--log-path", default=os.environ.get("RAG_EVAL_LOG_PATH"), help="Optional custom run.log output path")
    parser.add_argument("--gt-path", default=os.environ.get("RAG_EVAL_GT_PATH"), help="Optional custom ground truth path")
    return parser.parse_args()


def _load_existing_qids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    existing_qids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            qid = payload.get("qid")
            if qid:
                existing_qids.add(str(qid))
    return existing_qids


def resolve_output_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    out_path = Path(args.out_path) if getattr(args, "out_path", None) else OUT_PATH
    log_path = Path(args.log_path) if getattr(args, "log_path", None) else LOG_PATH
    return out_path, log_path


def resolve_ground_truth_path(args: argparse.Namespace) -> Path:
    return Path(args.gt_path) if getattr(args, "gt_path", None) else GT_PATH


def select_questions(
    questions: list[dict],
    qids: list[str] | None,
    offset: int,
    limit: int | None,
    existing_qids: set[str] | None = None,
    skip_existing: bool = False,
) -> list[dict]:
    selected = list(questions)
    if qids:
        allowed = {qid.strip() for qid in qids if qid and qid.strip()}
        selected = [question for question in selected if question.get("qid") in allowed]

    if skip_existing and existing_qids:
        selected = [question for question in selected if question.get("qid") not in existing_qids]

    safe_offset = max(0, int(offset or 0))
    if safe_offset:
        selected = selected[safe_offset:]

    if limit is not None:
        selected = selected[: max(0, int(limit))]

    return selected


def _prepare_conversation_setup(conversation_setup: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for turn in conversation_setup or []:
        if not isinstance(turn, dict):
            continue
        query = (turn.get("query") or turn.get("question") or "").strip()
        if query:
            normalized.append({"query": query})
    return normalized


def _prepare_setup_payloads(question: dict) -> list[dict]:
    session_id = question.get("session_id")
    payloads: list[dict] = []
    for turn in _prepare_conversation_setup(question.get("conversation_setup")):
        payloads.append(_build_request_payload({**turn, "session_id": session_id}))
    return payloads


def _ensure_backend_import_path() -> None:
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def _require_api_key() -> None:
    load_dotenv(BACKEND_DIR / ".env", override=True)
    api_key = os.environ.get("LANGEXTRACT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("Missing DEEPSEEK API key (LANGEXTRACT_API_KEY or DEEPSEEK_API_KEY)")


def _load_test_client() -> TestClient:
    _ensure_backend_import_path()
    from server import app

    return TestClient(app)


def _build_execution_path() -> str:
    return (
        "POST /api/v1/rag/query via fastapi.testclient.TestClient(server.app) "
        "(primary GraphRAG path; include_sources=true)"
    )


def _build_request_payload(question: str | dict) -> dict:
    if isinstance(question, dict):
        query = question.get("query") or question.get("question") or ""
        session_id = question.get("session_id")
    else:
        query = question
        session_id = None

    return {
        "query": query,
        **({"session_id": session_id} if session_id else {}),
        "options": {
            "include_sources": True,
            "language": "ch",
        },
    }


def _truncate_source_text(value: str, limit: int = 240) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _apply_response_payload(record: dict, payload: dict) -> None:
    sources = payload.get("sources") or []
    metadata = payload.get("metadata") or {}
    answer = payload.get("answer") or ""

    record["retrieved_node_ids"] = extract_retrieved_node_ids_from_rag_sources(
        sources,
        metadata=metadata,
    )
    record["num_sources"] = len(sources)
    record["activity_count"] = len(sources)
    record["final_answer"] = answer
    record["answer_node_ids"] = extract_node_ids_from_text(answer)
    record["tokens"] = normalize_token_usage(metadata.get("token_usage"))
    record["runtime_metadata"] = metadata
    record["path_hit_node_ids"] = metadata.get("path_hit_node_ids") or {}
    record["pre_rerank_node_ids"] = metadata.get("pre_rerank_node_ids") or []
    record["final_context_node_ids"] = metadata.get("final_context_node_ids") or []
    record["source_labels"] = [
        str(source.get("label") or "").strip()
        for source in sources
        if str(source.get("label") or "").strip()
    ]
    record["source_text_snippets"] = [
        _truncate_source_text(str(source.get("text_snippet") or source.get("text") or ""))
        for source in sources
        if str(source.get("text_snippet") or source.get("text") or "").strip()
    ]
    record["session_id"] = metadata.get("session_id") or record.get("session_id")
    record["rewritten_query"] = metadata.get("rewritten_query")
    record["rewrite_reason"] = metadata.get("rewrite_reason")
    record["latency_ms"] = int(metadata.get("duration_ms") or record.get("latency_ms") or 0)


def main() -> None:
    args = parse_args()
    _require_api_key()
    execution_path = _build_execution_path()
    out_path, log_path = resolve_output_paths(args)
    gt_path = resolve_ground_truth_path(args)

    with gt_path.open("r", encoding="utf-8") as handle:
        gt = json.load(handle)
    existing_qids = _load_existing_qids(out_path) if args.append and args.skip_existing else set()
    questions = select_questions(
        gt["questions"],
        qids=args.qids,
        offset=args.offset,
        limit=args.limit,
        existing_qids=existing_qids,
        skip_existing=args.skip_existing,
    )
    print(f"[GT] loaded {len(questions)} questions")
    print(f"[GT] path={gt_path}")
    print(f"[EXEC] {execution_path}")
    print(
        f"[MODE] append={args.append} skip_existing={args.skip_existing} "
        f"offset={args.offset} limit={args.limit} qids={args.qids or 'ALL'}"
    )
    print(f"[OUT] raw_runs={out_path}")
    print(f"[OUT] run_log={log_path}")

    log_mode = "a" if args.append else "w"
    out_mode = "a" if args.append else "w"

    with _load_test_client() as client, log_path.open(log_mode, encoding="utf-8") as logf, out_path.open(out_mode, encoding="utf-8") as outf:
        logf.write(f"=== RUN {datetime.now().isoformat()} ===\n")
        logf.write(f"execution_path={execution_path}\n")
        logf.write(f"ground_truth_path={gt_path}\n")
        logf.write(
            f"append={args.append} skip_existing={args.skip_existing} "
            f"offset={args.offset} limit={args.limit} qids={args.qids or 'ALL'}\n"
        )

        for index, question in enumerate(questions, start=1):
            qid = question["qid"]
            query = question["question"]
            print(f"\n[{index:02d}/{len(questions)}] {qid} ({question['category']}) {query[:60]}")
            logf.write(f"\n--- {qid} {question['category']} ---\nQ: {query}\n")
            logf.flush()

            record = {
                "qid": qid,
                "category": question["category"],
                "query": query,
                "should_refuse": question.get("should_refuse", False),
                "expected_node_ids": question.get("expected_node_ids", []),
                "execution_mode": "backend_rag_query_endpoint",
                "execution_path": execution_path,
                "retrieved_node_ids": [],
                "path_hit_node_ids": {},
                "pre_rerank_node_ids": [],
                "final_context_node_ids": [],
                "tool_calls": [],
                "num_tool_calls": 0,
                "num_sources": 0,
                "activity_count": 0,
                "activity_type": "retrieved_sources",
                "final_answer": "",
                "answer_node_ids": [],
                "latency_ms": 0,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "runtime_metadata": {},
                "session_id": question.get("session_id"),
                "source_labels": [],
                "source_text_snippets": [],
                "rewritten_query": None,
                "rewrite_reason": None,
                "http_status": None,
                "error": None,
                "timestamp": datetime.now().isoformat(),
            }

            t0 = time.time()
            try:
                for setup_payload in _prepare_setup_payloads(question):
                    setup_response = client.post("/api/v1/rag/query", json=setup_payload)
                    setup_response.raise_for_status()
                response = client.post(
                    "/api/v1/rag/query",
                    json=_build_request_payload(question),
                )
                record["http_status"] = response.status_code
                response.raise_for_status()
                payload = response.json()
                _apply_response_payload(record, payload)
                if record["latency_ms"] == 0:
                    record["latency_ms"] = int((time.time() - t0) * 1000)
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                if record["latency_ms"] == 0:
                    record["latency_ms"] = int((time.time() - t0) * 1000)
                logf.write(f"ERROR: {record['error']}\n{traceback.format_exc()}\n")
                print(f"   [ERROR] {record['error']}")

            outf.write(json.dumps(record, ensure_ascii=False) + "\n")
            outf.flush()

            answer_preview = (record["final_answer"] or "")[:120].replace("\n", " ")
            print(
                f"   sources={record['num_sources']} "
                f"retrieved={len(record['retrieved_node_ids'])} "
                f"tokens={record['tokens']['total']} "
                f"latency={record['latency_ms']}ms"
            )
            print(f"   ans: {answer_preview}")
            logf.write(
                f"http_status={record['http_status']} "
                f"sources={record['num_sources']} "
                f"retrieved={record['retrieved_node_ids']}\n"
                f"latency_ms={record['latency_ms']} tokens={record['tokens']}\n"
                f"answer: {record['final_answer'][:400]}\n"
            )
            logf.flush()

    print(f"\nDONE -> {out_path}")
    print(f"LOG -> {log_path}")


if __name__ == "__main__":
    main()
