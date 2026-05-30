# Harness Engineering Skill Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify `harness-engineering` branding and 7-layer semantics across evaluation and reference docs while preserving historical benchmark outcomes.

**Architecture:** Apply documentation-only, minimal-scope edits in the skill package and keep benchmark scores unchanged. First fix objective metadata mismatches (`skill_name`, `skill_path`, stale naming), then align language drift (7-layer wording and layer index references), then remove residual legacy terms in explanatory docs. Verify via grep-based checks and JSON validity checks after each task.

**Tech Stack:** Markdown/JSON edits, Git, shell verification (`rg`, `jq`, `git diff`)

---

## File Structure and Responsibilities

- `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json`
  - Benchmark metadata authority for skill identity and path.
- `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`
  - Human-readable benchmark summary and notes.
- `C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md`
  - Long-form methodology reference; must match current skill naming and layer semantics.
- `C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json`
  - Eval prompt/expectation contract; wording must be internally consistent with canonical Layer 0-6 model.

---

### Task 1: Correct Benchmark Metadata Identity

**Files:**
- Modify: `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json`
- Test: `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json` (JSON parse)

- [ ] **Step 1: Write the failing metadata check**

Run:

```bash
jq -r '.metadata.skill_name, .metadata.skill_path' C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
```

Expected before fix:

```text
harness-engineering
C:/Users/14156/.claude/skills/harness-engineering
```

- [ ] **Step 2: Apply minimal metadata fix**

Replace this JSON fragment:

```json
"metadata": {
  "skill_name": "harness-engineering",
  "skill_path": "C:/Users/14156/.claude/skills/harness-engineering",
```

With:

```json
"metadata": {
  "skill_name": "harness-engineering",
  "skill_path": "C:/Users/14156/.claude/skills/harness-engineering",
```

- [ ] **Step 3: Verify metadata now passes**

Run:

```bash
jq -r '.metadata.skill_name, .metadata.skill_path' C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
```

Expected after fix:

```text
harness-engineering
C:/Users/14156/.claude/skills/harness-engineering
```

- [ ] **Step 4: Validate JSON integrity**

Run:

```bash
jq empty C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
```

Expected: exit code 0 and no output.

- [ ] **Step 5: Commit**

```bash
git add C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
git commit -m "docs(eval): align benchmark metadata with harness-engineering identity"
```

---

### Task 2: Correct Benchmark Summary Branding and Layer Note

**Files:**
- Modify: `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`
- Test: `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md` (content grep)

- [ ] **Step 1: Write the failing content checks**

Run:

```bash
rg -n "harness-engineering|following [0-9]+-layer methodology explicitly" C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
```

Expected before fix: at least one match for title branding and one for layer note.

- [ ] **Step 2: Apply title/notes wording fix**

Replace heading:

```markdown
# Skill Benchmark: harness-engineering
```

With:

```markdown
# Skill Benchmark: harness-engineering
```

Replace note line:

```markdown
- with-skill responses are more thorough (2x tokens) and better structured, following 7-layer methodology explicitly
```

With:

```markdown
- with-skill responses are more thorough (2x tokens) and better structured, following the Layer 0-6 methodology explicitly
```

- [ ] **Step 3: Verify wording now passes**

Run:

```bash
rg -n "harness-engineering|following [0-9]+-layer methodology explicitly" C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
```

Expected after fix: no matches.

- [ ] **Step 4: Commit**

```bash
git add C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
git commit -m "docs(eval): update benchmark summary branding and layer wording"
```

---

### Task 3: Remove Legacy Naming in Reference Methodology

**Files:**
- Modify: `C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md`
- Test: `C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md` (content grep)

- [ ] **Step 1: Write the failing legacy-name check**

Run:

```bash
rg -n "harness-engineering" C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md
```

Expected before fix: one or more matches (notably table label in Layer 5 section).

- [ ] **Step 2: Apply minimal rename without semantic drift**

Replace table header row segment:

```markdown
| 子系统 | harness-engineering 对应物 | 自检问题 |
```

With:

```markdown
| 子系统 | harness-engineering 对应物 | 自检问题 |
```

- [ ] **Step 3: Verify name cleanup**

Run:

```bash
rg -n "harness-engineering" C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md
```

Expected after fix: no matches.

- [ ] **Step 4: Commit**

```bash
git add C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md
git commit -m "docs(reference): remove residual legacy skill naming"
```

---

### Task 4: Fix Eval Layer Index Wording Drift

**Files:**
- Modify: `C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json`
- Test: `C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json` (consistency grep + JSON parse)

- [ ] **Step 1: Write the failing wording checks**

Run:

```bash
rg -n "Layer 3|Layer 5|Layer 6|BridgePipeline" C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
```

Expected before fix: line containing expectation text that maps BridgePipeline to Layer 3 and blueprint/spec steps to Layer 5/6 wording.

- [ ] **Step 2: Apply precise expectation wording corrections**

Replace expectation entry:

```json
"响应中正确评估了MinerU与LangExtract之间的桥接状态：若桥接尚未完成则建议先建立BridgePipeline（Layer 3），若桥接已完成则确认状态并引导进入产品蓝图阶段（Layer 5）"
```

With:

```json
"响应中正确评估了MinerU与LangExtract之间的桥接状态：若桥接尚未完成则建议先建立BridgePipeline（Layer 2），若桥接已完成则确认状态并引导进入产品蓝图阶段（Layer 4）"
```

Replace expectation entry:

```json
"响应中建议在写产品代码之前生成PRD和后端API规范（Layer 5）"
```

With:

```json
"响应中建议在写产品代码之前生成PRD和后端API规范（Layer 4）"
```

Replace expectation entry:

```json
"响应中建议确立项目目录结构和开发规范（Layer 6）：frontend/、backend/、.env管理、uv虚拟环境"
```

With:

```json
"响应中建议确立项目目录结构和开发规范（Layer 5）：frontend/、backend/、.env管理、uv虚拟环境"
```

- [ ] **Step 3: Verify wording and parse**

Run:

```bash
rg -n "Layer 3\)|Layer 5\)|Layer 6\)" C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
jq empty C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
```

Expected after fix:
- grep returns only semantically correct occurrences.
- `jq empty` returns exit code 0.

- [ ] **Step 4: Commit**

```bash
git add C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
git commit -m "docs(eval): align layer references with canonical 0-6 model"
```

---

### Task 5: Cross-File Consistency and Non-Regression Verification

**Files:**
- Test only:
  - `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json`
  - `C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`
  - `C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md`
  - `C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json`

- [ ] **Step 1: Run global legacy-token scan**

```bash
rg -n "harness-engineering|legacy-layer-wording" C:/Users/14156/.claude/skills/harness-engineering/evals C:/Users/14156/.claude/skills/harness-engineering/references
```

Expected: no unintended residual matches in remediated scope.

- [ ] **Step 2: Ensure benchmark scores unchanged**

Run:

```bash
jq '.run_summary, .runs[].result' C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json > /tmp/benchmark_after.json
git show HEAD~4:C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json | jq '.run_summary, .runs[].result' > /tmp/benchmark_before.json
diff -u /tmp/benchmark_before.json /tmp/benchmark_after.json
```

Expected: no differences in score/time/token/result blocks.

- [ ] **Step 3: Confirm change scope**

Run:

```bash
git diff --name-only HEAD~4..HEAD
```

Expected:

```text
C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md
C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
```

- [ ] **Step 4: Final commit (only if previous tasks were squashed locally)**

```bash
git status --short
```

Expected: clean working tree. If not clean due to intentional final edits, add and commit with:

```bash
git add C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json C:/Users/14156/.claude/skills/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md C:/Users/14156/.claude/skills/harness-engineering/references/methodology.md C:/Users/14156/.claude/skills/harness-engineering/evals/evals.json
git commit -m "docs: finalize harness-engineering terminology and layer consistency remediation"
```

---

## Self-Review

- Spec coverage check:
  - Covers stale branding in benchmark artifacts.
  - Covers 7-layer vs old wording drift in eval and summary docs.
  - Covers residual legacy term in reference methodology.
  - Preserves historical benchmark numerical outputs by verification step.
- Placeholder scan:
  - No TODO/TBD placeholders.
  - Each step includes exact commands and expected outcomes.
- Type/field consistency:
  - Uses exact field names: `metadata.skill_name`, `metadata.skill_path`, `expected_output`, `expectations[]`.
  - Layer mapping remains canonical: Layer 2 bridge, Layer 4 blueprints, Layer 5 engineering rules.
