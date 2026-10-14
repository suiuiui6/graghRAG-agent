# Isolated Runtime Capture Implementation Plan

> **For agentic workers:** Use subagent-driven-development for bounded coding tasks with separate spec and quality review. No commits, worktree, installation or production edits: the author chose a project-local physical runtime copy.

**Goal:** Prepare a physically independent runtime and capture offline query context only after verified process-specific network isolation, preserving original assets and M2_OPEN.

**Architecture:** Snapshot preparation is separate from an elevated firewall supervisor and unprivileged capture child. Unique real Python executable; rule evidence, side effects and cleanup are explicit gates. Author approval does not prove OS privileges.

**Tech Stack:** Existing Python 3.12, pathlib/hashlib/shutil/sqlite3, pytest, Windows PowerShell NetSecurity. No remote services, installations or fake embeddings.

## Authorization and preflight

Author authorized dedicated-executable temporary outbound rules on 2026-10-08, followed by exact-rule removal. Current process is not administrator outside the sandbox. Firewall profiles are enabled and permit local rules. No rule changed. UAC may be required; never request credentials or disable global firewall. Design: docs/superpowers/specs/2026-10-08-isolated-runtime-capture-design.md.

## Task 1: physical snapshot preparation

Files: backend/research/isolation_snapshot.py, backend/tests/test_isolation_snapshot.py. No production modifications.

- [ ] TDD for unique target/no overwrite, containment, reparse/hardlink/secret rejection, independent entity copies and matching hashes, source drift, nonzero WAL abort, no nested research-isolation recursion.
- [ ] Implement safe_files(base, paths), copy_verified(source, target), prepare_snapshot(root, run_id, base_python). Safe target: backend/output/research-isolation/<run_id>. No execution, firewall mutation or credential read.
- [ ] Code whitelist: backend root .py, routes/services/middleware/bot/migrations/research Python files, uv.lock/pyproject.toml as present. Exclude tests/bytecode/.env/log/private exports. Asset whitelist: output/vectordb, runtime, kg, mineru, embedding_cache; docs_store.json, runtime_cache.sqlite3, rewrite-cache.sqlite3 and runtime.db as present. Reject nonzero WAL rather than copying inconsistent DB. No historical answers.
- [ ] Dedicated runtime: real base python.exe + root DLLs, DLLs/, Lib/ excluding global site-packages/bytecode. Physically copy backend/.venv/Lib/site-packages (no bytecode/secret/log files or links). No venv launcher, hardlinks, shared writable dependencies or installation. Separate explicitly verified model cache input only.
- [ ] Metadata manifest: entity identities, origin/hash and before/after checks only. Partial destination retained on failure; never recursively deleted. No overwrite of existing run.
- [ ] Run focused pytest; independent spec review followed by quality review, then actual snapshot preparation.

Command: backend/.venv/Scripts/python.exe -B -m pytest backend/tests/test_isolation_snapshot.py -q -p no:cacheprovider. Unit tests are not production capture evidence; report the existing timeout warning separately.

## Task 2: firewall supervisor and capture guard

Files: backend/research/isolated_firewall.ps1, backend/research/isolated_capture.py and targeted tests. Implement only if privilege handoff is safely available; otherwise preserve prepared assets and report BLOCKED_ADMIN_TOKEN with operation companion.

- [ ] TDD: reject shared exe, collisions, wrong run/manifest identity, incomplete active profiles, stale receipts, out-of-snapshot writes, missing cleanup and external child execution.
- [ ] Supervisor validates exact physical executable/hash. Unique block-outbound rule for that program only, all protocols/addresses/profiles; inspect ActiveStore/filter. No global policy modifications. Receipt binds controller/rule/path/hash.
- [ ] Only elevated supervisor changes rules; runtime stays unprivileged. Bounded lifetime; finally removes only owned exact-name rule, verifies absence. Never remove collision/preexisting rules.
- [ ] Before service imports: whitelisted environment, no credentials/shared writable paths, snapshot-only writes/cache, no sockets/DNS/child process, bytecode off, local-files-only models. Guards supplement rather than replace OS firewall.
- [ ] No internet test request. Local rule inspection and guarded rejection tests only. Stop if enforcement/program identity/helper process boundary cannot be verified.

## Task 3: capture and evidence

- [ ] Verify code-side effects/runtime paths and available local models without downloads. Resource failure blocks rather than changes baseline.
- [ ] After network gate launch dedicated unprivileged Python, record actual executable/cwd/module/lock hashes and loaded corpus. Original startup mutations may affect only copy; record frozen vs recovered corpus separately.
- [ ] Exact v2 questions/new sessions. Preserve native retrieval/rescue/rerank/budget/prompt. At actual generation boundary capture final messages/mappings then stop before send. Deterministic short-circuit stays NOT_SENT. Original remote-preprocess exception fallback is OFFLINE_NATIVE_FALLBACK_CONTEXT, not normal online B0 or actual model-visible context.
- [ ] Verify original freeze/index/sidecars, no external sends, child exit and rule removal. Private context stays under ignored output/research-isolation. Public audit under scope-pilot/local-v2-tools; M2 OPEN and M4 P2 preserved.

## Stop conditions

Privilege denial, missing model/runtime, unsafe config, unverifiable firewall, path escape, source drift, inconsistent SQLite or unresolved review. Finish independent preparation where safe; no repeated broad approval requests. No service startup before gate. Prepared files or mocked tests never count as native capture.
