# Final R5 consumer review preparation

Read-only preparation 2026-10-14; no active R5 source executed. Await root's frozen snapshot.

Consumer inputs currently read:

- backend/retrieval.py SHA256 2f0761dcb736f63ba6e688c9749057fb60ee419ce2f33541969e4e8cde7bd0e1
- backend/source_control.py SHA256 b92d65ad4604207c0bdc65670197a3c63c37c668abacb8d6b38451d025001c25
- backend/vector_store.py SHA256 18d8fc6ff90823186034f5f10c876981a0da814bba5bb57c9299400eec0a6c82

Independent execution plan after snapshot receipt:

1. Verify source manifest and old R4b 110 hashes; copy snapshot to private reviewer workspace. Never execute archived scripts pointing at old freezes without inspecting their output paths.
2. Load actual AST functions from current retrieval with future annotations and source hash receipts: _search_vector_store_with_projection, _vector_recall, multi_path_recall. Load actual source_control source_allowed/source_skip_reason/record_source. Avoid importing product config/provider modules or loading .env. Dependencies supplied as software harness globals must be recorded; this is actual function execution, not full API integration.
3. Test successful record identity/text projection, real zero match, actual candidate storage exception, ValueError/TypeError native compile injections. Assert one search attempt for failures, storage code and cause identity; assert explicit legacy-signature Store still uses fallback. One query vector prevents genuine second-vector recall from being confused with retry.
4. Execute actual multi_path_recall with vector-only config, actual ThreadPoolExecutor, and actual candidate against synthetic store. Assert empty success status=executed/candidate_count=0; failure status=failed/reason=recall_failed/candidate_count=None. An AST harness with no actual candidate remains software boundary evidence only.
5. Check invalid filter/input never enters backend; homogeneous raw type vs first parsed numeric type; signed I64 metadata vs query >U64 finite conversion; scalar NaN/Inf; bool not silently treated as integer; dimension, nonfinite vector, length mismatch ValueError with safe phrase. Preserve typed numeric success semantics and raw/compat bits.
6. New independent real Chroma/Lance input in locked environments requires require_escalated offline. Do not retry sandbox asyncio hang. Distinguish actual bad-path failures from deterministic injections.
7. Examine logger.warning(exc_info=True) at retrieval.py:560 through actual logging_config.py processor order format_exc_info -> redact_sensitive -> JSONRenderer. Scrubber exists; full raw cause content does not by itself establish final output leakage. Test both recognizable sensitive patterns and unrecognized synthetic markers; report actual measured final output. Safe str/fields alone does not establish log safety. Record scope; production logger changes are outside this task.
8. Worker/API/multi-query-provider/native security/formatter global equivalence remain NOT_RUN or OPEN unless actually exercised. Final review references tested snapshot and command exit codes.

Note: retrieval rescue loop currently covers kg/bm25/table, not vector storage. Do not claim this loop as actual vector rescue coverage. Existing vector rescue tests often inject embedding errors, not storage errors.
