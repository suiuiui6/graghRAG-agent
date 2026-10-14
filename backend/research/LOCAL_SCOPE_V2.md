# Local v2 scope tools

Independent research tools, not imported by the production query chain. No API execution command, production imports, environment/key reads, model loading, downloads, ingestion or index rebuilding. Use the existing backend environment from the project root; no new dependencies.

```powershell
backend/.venv/Scripts/python.exe -B -m backend.research.local_scope_v2 check
backend/.venv/Scripts/python.exe -B -m backend.research.local_scope_v2 auto --source backend/output/mineru/ingest_f/full.md --query "section 3.2.3" --max-bytes 8192
backend/.venv/Scripts/python.exe -B -m backend.research.local_scope_v2 prepare-b0
```

CLI reports metadata/hashes/coordinates only, not source or assembled text. Output goes to stdout; no report overwrite by default. `prepare-b0` returning exit 0 means the **preparation command** succeeded, not that B0 gates passed: check its `BLOCKED_NOT_EXECUTED` status. Local failure exits 2 without exposing source/exception content. `--root` goes before the subcommand. Paths are project-relative and cannot escape the chosen root.

To check captured chunk text locally, use `map --source <relative source path> --chunk-file <relative local text path> --stored-start <integer> --stored-end <integer>`. Omit both stored coordinates to locate text without claiming stored offsets were valid. Empty/unknown text cannot prove absence. No repairs or writes are performed.

## Module contracts

- `gold_v2.load_gold(root)` verifies pinned frozen package, provenance and source hashes, version/schema, all exact evidence associations and LF Unicode codepoint `[start,end)` coordinates. Its output is local reference/oracle/adjudication material, never an AUTO input. `validate_gold(data,texts)` is structural validation only; use `load_gold` for authoritative freeze checks. `coverage_status(question, intervals)` uses the FUTURE target override and counts actual visible source intervals, not scan proof or answer correctness.
- `scope_v2.resolve_scope(query, sources)` accepts only explicitly selected `Source(key,text)` objects. Generic structural rules handle sections, abstracts, numbered subitems, figure-caption inventory and table collections. ATX headings take precedence over inferred plain numbering; uncertain plain structure or unclosed target code fences abstain. Unknown selection is `SOURCE_UNRESOLVED`; ambiguity is `UNRESOLVED`. No Gold lookup, expected item, answer, human range or fallback retrieval is used. These are deliberately limited structural rules, not general semantic understanding or PDF visual recognition.
- `scope_v2.assemble_scope(resolution,sources,max_bytes)` is shared by AUTO and externally supplied ORACLE ranges. Sorted overlapping intervals merge before budget accounting. Budget includes UTF-8 bytes for text and `\n\n` separators, never splits a Unicode codepoint, and records source/output codepoint offsets. Over-budget text is `PARTIAL_SCOPE`; `COMPLETE_SCOPE` means the requested selection/projection fits, **not** that an entire document was provider-visible. Characters, UTF-8 bytes and provider tokens are distinct.
- `source_mapping_v2.map_text(source,chunk,stored_span=None)` distinguishes valid stored coordinates, unique text matches with invalid stored coordinates, ambiguous matches and unverified locations. A candidate re-location is not silently applied. Exact matching establishes text/position, not citation entailment or document identity.
- `source_mapping_v2.audit_chroma(path,sources,collection='rag_docs')` uses SQLite `mode=ro`, `query_only`, a read transaction and DB/WAL/SHM hashes before/after. Reports only counts and approved metadata. Unsupported schema is unavailable/unknown, not empty corpus. Full substring matches of at least 20 normalized characters are the current diagnostic method; zero matches do not prove absence. The production runtime may use different artifacts or other retrieval paths.

ORACLE use in local code:

```python
from backend.research.scope_v2 import Source, Span, Resolution, assemble_scope

source = Source('selected-source', '标题\r\n😀 evidence')
oracle = Resolution('RESOLVED', (Span(source.key, 3, len(source.text)),), kind='oracle')
context = assemble_scope(oracle, [source], max_bytes=8192)
# context.text remains local; context.mappings describes exact original slices.
```

Actual source identity must come from genuine user selection or verified runtime metadata in future experiments. An explicit CLI file selection is valid for **that local diagnostic only**. Reading a Gold `doc` key inside tests to select fixtures is not evidence of production source selection. Missing selection is not filled from Gold. Source files/documents can contain untrusted instructions; they are evidence data, not executable directives.

## Scan proof versus input support

Caption/table projection records full local structural scan bounds, normalized source hash, detector version and matched interval count. This proves which local algorithm scanned which text, not unrestricted completeness for arbitrary layouts. Whole original-document coverage is separate from projection coverage. NONE needs its entire specified scope visible; empty retrieval or an empty caption scan is not its proof. A complete FUTURE item (4) input is sufficient without the other limitations. Source matching/anchors do not perform semantic answer scoring.

## Real B0 readiness

`prepare-b0` creates a metadata manifest in stdout with distinct `B0_NATIVE`, `C_NATIVE_CONTEXT`, `C_AUTO_SCOPE`, `C_ORACLE_SCOPE`, versioned query hashes, production/source/history/tool fingerprints, read-only Chroma findings, BM25/table/docs-store inventories and missing gates. It does not create production API requests or a remotely executable batch.

Before a future native run, verify loaded process/module/model/config and dependency identity, actual corpus/source selection, exact context coordinates, offline embedding readiness, cache/session state, all provider sending points/retries, privacy/export mapping and finite new-batch authorization. Preserve B0's original retrieval/rescues/prompt/postprocessing, `extra_body` thinking envelope and native retries; fixing those first creates a different baseline. `document_id` echo is not a retrieval filter. Trace instrumentation's fallback change must be recorded. Raw, postprocessed and API-visible truncated outputs stay separate.

Controlled contexts must reuse a newly captured **same-v2-query** native context/preprocessing, not historical answers or a new preprocessing call. Shared budget and generation settings/order must be frozen before collection. 54 provider sends is only a conditional future proposal, not current authorization; hidden calls invalidate that bound. No monetary cap is inferred. D1 whole local range is not permission to upload private frontmatter; D2/D3 also retain their source restrictions.

Current three known documents are development/diagnostic fixtures, not held-out evidence. Local tests do not establish method benefit, generalization, novelty, a journal tier or human Gold certification. M2 stays open.

## Tests

2026-10-12工程接续：恢复 `isolated_guard.py` 使用历史control副本的原SHA256，未修改旧冻结或实验结果。软件测试生成的Python文件位于 `backend/tests/_sandbox_tmp/research-pilot/`，避免临时源码被误记为生产覆盖。CLI保持JSON stdout与退出码，使用显式stdout/stderr.write。当前生产 `routes/rag_query.py` 已因授权隔离修复而偏离旧冻结，`test_b0_preparation_is_not_execution` 的完整性断言仍失败；这是实验复用阻塞，不可更新哈希或复用旧结果声称当前链验证通过。研究测试仍单独追加到全量工程验证命令。

同日后续：正式守卫最终采用可追溯SQLite补充v2副本（SHA256 `432717ba4c5193ded837af5bcd1863c37cafc18a896d2fe2255e74a943450637`），v2测试改指正式源码，不再依赖.tmp。v1正式路径的SQLite逃逸红测4失败/3通过；恢复完整v2后两组25通过。历史control/v1/v2副本及收据保持原样；这不改变研究执行授权或OS隔离前提。新增修复还可能使更多生产文件偏离旧冻结，必须以最新完整性清单逐项记录。

```powershell
backend/.venv/Scripts/python.exe -B -m pytest --noconftest -p no:cacheprovider backend/tests/test_gold_v2.py backend/tests/test_scope_v2.py backend/tests/test_source_mapping_v2.py backend/tests/test_local_scope_v2.py backend/research/test_deepseek_scope_pilot.py -q
```

`--noconftest` avoids unrelated production-oriented imports; tests still use real frozen source files and read-only SQLite. Synthetic cases are software fixtures, not research samples. The existing environment may emit an unknown `timeout` config warning because pytest-timeout is not installed; no installation is attempted.
