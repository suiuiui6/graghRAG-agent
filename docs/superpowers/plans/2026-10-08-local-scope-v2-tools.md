# Local scope v2 tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Existing two-track design is approved; current-directory implementation on master explicitly approved by user option 1. No commits, network, service imports, index writes or production edits.

**Goal:** Verify frozen v2 locally, assemble honest bounded contexts, validate source locations, and prepare (not execute) native B0.

**Architecture:** Independent AUTO module consumes query and selected source structure only. Gold loader is restricted to reference/oracle/adjudication; both AUTO and ORACLE use one assembler. Exact mapping and read-only SQLite audits do not repair indexes or imply corpus completeness.

**Tech Stack:** Existing Python 3.12, PyYAML, unittest/pytest, standard-library hashlib/sqlite3/argparse. No dependency installs.

## Task 1: Frozen loader

Files: `backend/research/gold_v2.py`, `backend/tests/test_gold_v2.py`.

- [x] Write tests: `package = load_gold(root); assert package.summary['questions'] == 9`; check 31 items, 125 required/25 optional attributes, 172 evidence associations; FUTURE target override; changed hash, invalid span, schema and path traversal rejection.
- [x] Run `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_gold_v2.py -q --noconftest`; verify missing implementation failure.
- [x] Implement `load_gold(root, gold_path=None, freeze_path=None)` with frozen artifact hashes, raw-byte and normalized source hashes, codepoint spans, exact evidence and scope checks. Never print source content.
- [x] Rerun tests; retain immutable historical artifacts.

## Task 2: Independent scope resolver and shared assembler

Files: `backend/research/scope_v2.py`, `backend/tests/test_scope_v2.py`.

- [x] Test `resolve_scope(query, sources)` for explicit section, numbered subitem, abstract, full document, caption inventory and table collections. Check missing selection, duplicate headings, table-vs-figure distinction, ambiguity, malformed boundaries.
- [x] Run the new test module with `--noconftest` before implementation.
- [x] Implement `Source`, `Span`, `Resolution`, `Assembly`, `resolve_scope`, `assemble_scope`. No Gold imports, qid lookup, manual ranges, expected answers or production imports in AUTO. Sources supplied here represent explicit selection, not Gold document IDs.
- [x] Test common UTF-8 budget accounting including separators, non-BMP Unicode, CRLF normalization, ordered nonoverlapping spans, honest partial truncation, export-to-source mappings, complete local scan proof versus input coverage. AUTO and ORACLE call the same assembler.
- [x] Rerun tests and real-source local checks; resolved routes are software observations, not scientific performance claims.

## Task 3: Mapping and read-only corpus checks

Files: `backend/research/source_mapping_v2.py`, `backend/tests/test_source_mapping_v2.py`.

- [x] Write tests: repeated text is ambiguous; a valid claimed coordinate is exact; a bad coordinate is not silently repaired; empty text cannot prove absence; SQLite opened read-only with query_only leaves file hash unchanged.
- [x] Run test module to observe missing implementation failure.
- [x] Implement exact occurrence enumeration and separate stored-coordinate validation; unknown/transformed text is LOCATION_UNVERIFIED, not absence or model failure. SQLite reader exposes only chunk text/metadata needed for local matching, never credentials or public source text.
- [x] Rerun tests using synthetic mapping cases and a local production SQLite snapshot read-only (no writable synthetic database was needed).

## Task 4: Offline entry point and B0 readiness

Files: `backend/research/local_scope_v2.py`, `backend/research/LOCAL_SCOPE_V2.md`, `backend/tests/test_local_scope_v2.py`.

- [x] Write tests for local summary JSON, no source/private text by default, explicit selected-source AUTO only, not-executed B0 manifest and unresolved readiness gates. No B0 execute command.
- [x] Run test module to observe missing feature failure.
- [x] Implement `python -m backend.research.local_scope_v2 check` and `prepare-b0`: stdout metadata only, no new provider calls, runtime/corpus/source selection/transfer authorization unknown unless evidenced. Four path names distinct; native retry/preprocess/request envelope must be preserved, captured same-version contexts reused only.
- [x] Rerun all four modules and legacy research tests. Independently review implementation, verify freeze/source/production/history hashes, write measured results/readiness documentation. M2 stays open; no novelty/generalization claim.

## Delivery checkpoint

- [x] Record fresh commands and observed test counts.
- [x] Native B0 remains NOT_EXECUTED; corpus membership and runtime verification must precede new API authorization/execution.
- [x] Preserve all existing user changes and the other worktree; do not commit or push.
