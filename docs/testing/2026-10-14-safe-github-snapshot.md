# 2026-10-14 GitHub diagnostic snapshot publication scope

This is a reviewed diagnostic source/evidence snapshot, not a production release or deployment approval. Source checkout: local commit `33adcc4`; publication branch: `codex/safe-snapshot-20261014`.

The publication uses an orphan root commit because both local unpublished history and the existing remote main history contain tracked environment-file objects. Existing local and remote branches are preserved; this operation does not clean or rewrite those histories. Only the new branch is authorized for push.

The reviewed initial tree contains 1,952 ordinary files and two unchanged remote-baseline gitlink identities. It excludes `.claude/goal-state.json`, `.claude/settings.json`, `.lra/feature-list.json`, `.lra/init.sh`, `.lra/progress.txt`, and `frontend/tsconfig.tsbuildinfo`. Untracked private files and dirty child-repository contents are not copied. Gitlinks do not constitute a child-repository security or reproducibility audit. `.gitattributes` preserves exact audited bytes and frozen evidence hashes.

The full offline scan produced 16,258 findings; independent reconstruction explained all findings, with zero unmatched findings. Sixteen coverage databases were additionally inspected as SQLite coverage schemas; all 1,610 extracted text rows were scanned with zero findings. These are bounded reviews, not a guarantee about all historical or undetected content. See `docs/review/2026-10-14-safe-github-publish-review.md`.

Unchanged tested input hashes: backend 171, frontend 53, rag_eval 22; zero drift. Existing whole-scope evidence remains applicable: backend lines 12698/13568 and branches 4154/4584; frontend 927/957 and 853/913; rag_eval 1722/1742 and 415/440. Packaging did not rerun the full product suites. Current authoritative vector freeze manifests pass; two nested historical manifests retain their documented obsolete-root limitations.

Four unique Chroma advisories remain without fixes in the audited version. Native numerical boundaries, logging redaction, full adapter integration, live CI/protection and deployment remain subject to their existing documented limitations. Windows verification remains audit-only-windows. Uploading this snapshot closes none of those issues.

Final checks must bind the actual staged bytes and commit: explicit file whitelist, incremental documentation scan, zero production-input drift, no commit parents, exactly one reachable commit, and known old credential objects unreachable. Remote upload completion is recorded separately after an actual remote-ref comparison; this document does not preclaim a successful push.
