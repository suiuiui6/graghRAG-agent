# GraphRAG Agent 90-Day GitHub Growth Design

Date: 2026-09-09  
Status: approved design; implementation not started

## Goal

Increase GitHub Star growth over 90 days by making GraphRAG Agent the portfolio's
flagship entry point: understandable in 30 seconds, runnable offline in 5
minutes, and credible through reproducible evidence. Goal Skill and Harness
Engineering remain supporting governance projects rather than runtime
dependencies.

## Product position

GraphRAG Agent is a locally runnable multimodal document-to-knowledge-graph-
to-grounded-Q&A application. The first public experience must demonstrate the
core value without requiring MinerU, DeepSeek, Neo4j, OSS, or production
credentials.

The repository remains an application reference, not a hosted service. External
providers are explicit opt-in capabilities. Unavailable or unobserved behavior
is reported as `unconfigured` or `not-run`, never as a synthetic success.

## Scope and boundaries

### In scope

- README discovery path, screenshots/GIFs, and a 5-minute Quick Start.
- Offline fixture mode with public, reproducible sample data.
- Frontend loading, empty, success, and error states for the demo path.
- Backend offline smoke checks, health reporting, timeout/error behavior, and
  secret-safe logging.
- CI checks for public surface, frontend build, backend offline tests, and the
  offline demo smoke path.
- Getting-started, demo walkthrough, architecture, and evaluation documents.
- A first stable release candidate and community onboarding improvements.

### Out of scope

- Mandatory external providers, production deployment, hosted demo, accounts,
  billing, multi-tenancy, or cloud storage.
- Rewriting the GraphRAG extraction or retrieval algorithms.
- Making Goal/Harness a runtime dependency for application users.
- Forced React Router downgrade or a Node 20 migration in the first phase.
- Treating synthetic data, static checks, or process exit code 0 as observed
  Agent behavior or production evidence.

## Architecture

```text
React/Vite frontend
        | HTTP API
FastAPI backend
        |------------------|
  offline fixture       optional external providers
                       (MinerU, DeepSeek, Neo4j, OSS)
```

Offline fixtures are an additive test and onboarding path. They do not replace
the existing provider pipeline. Goal and Harness retain the one-way relationship
`Goal -> Harness -> GraphRAG delivery verification`; GraphRAG can run without
installing either governance repository.

## Data flow

```text
public sample document or pre-generated fixture
        -> offline parser/fixture loader
        -> entities, relations, source locations
        -> graph view and retrieval results
        -> grounded answer with source references
```

Each demo result records a fixture/document identifier, source location,
question, answer/result payload, and execution mode (`offline`, `provider`, or
`not-run`). Pre-generated data is explicitly demonstration data and is excluded
from claims about real provider or Agent behavior.

## Error and security behavior

- Missing provider configuration produces an actionable `unconfigured` state.
- Provider timeout produces a bounded error and retry guidance.
- Missing or malformed fixture fails fast with the required path.
- Frontend API failures render a recoverable error state rather than a blank page.
- External failures never fall back to fabricated success.
- Logs may include status, duration, and error category, but never credentials,
  access tokens, or complete environment/configuration values.
- `.env`, uploads, generated graphs, and logs remain ignored and outside commits.

## 90-day delivery phases

### Phase 1: days 1-14 — understandable and runnable

- Correct the public display name to `GraphRAG Agent`; retain the repository URL
  for compatibility unless a separate rename decision is approved.
- Add real UI screenshots or a short GIF and a shortest verified Quick Start.
- Implement the offline fixture path and one reproducible result.
- Add installation-failure guidance and move historical material behind docs links.
- Extend CI with frontend build, backend offline tests, and offline smoke.

Exit criteria: a clean environment can reach a successful offline result without
paid credentials; the README explains value, audience, limitations, setup, and
result appearance within the first screenful.

### Phase 2: days 15-45 — worth starring

- Publish version `v0.1.0` only after the Phase 1 evidence is green.
- Add two or three copyable use cases and a small offline evaluation report.
- Provide a pre-generated graph/sample dataset and Docker Compose or an equally
  short local launcher if it does not add unsafe operational complexity.
- Add FAQ, roadmap, known issues, and one complete technical walkthrough.

Exit criteria: each core feature has a reproducible example, version and
compatibility requirements are explicit, and offline evaluation results have a
documented data and limitation boundary.

### Phase 3: days 46-90 — community formation

- Maintain Discussions, Good First Issue, Help Wanted, and RFC labels.
- Publish progress updates at least every two weeks.
- Prioritize real onboarding blockers from issues and discussions.
- Add an optional Knowledge Manager integration example and a Goal/Harness
  delivery case study without making either a runtime dependency.

Exit criteria: at least one independent user can reproduce the demo and there is
evidence of real external feedback or contribution. Star count is an outcome,
not the sole acceptance criterion.

## Verification matrix

| Level | Evidence | Completion meaning |
|---|---|---|
| Contract | paths, routes, configuration, docs, ownership | required |
| Offline fixture | real frontend/backend processes and public sample data | required |
| Observed event | actual Agent/Skill reads and judgments | counted only when collected |
| Provider integration | MinerU, DeepSeek, Neo4j, OSS | opt-in; otherwise `not-run` |
| Browser E2E | real page interactions and error states | Phase 2/3 |
| Production | deployment, monitoring, recovery, capacity | outside this design |

## Success measures

### Technical

- README-to-first-result path uses no more than five core commands.
- Frontend production build exits 0.
- Backend offline smoke exits 0.
- Main and pull-request CI execute the same core offline checks.
- No public secret scan findings.

### Growth

- A first-time visitor can answer what/why/how/result from the README alone.
- At least one external user reproduces the offline demo without private help.
- Star growth is accompanied by real issues, discussions, examples, or
  contributions rather than artificial metrics.

## Rollback and risk

- Revert only the affected README, fixture, workflow, or release commit if a
  regression appears.
- Preserve existing provider routes and data formats while the offline path is
  evaluated.
- Do not force dependency upgrades that require breaking API changes; record
  remaining advisories and revisit them with a dedicated Node 20 migration plan.
- If offline and provider paths diverge, keep the evidence separate and repair
  the smallest affected layer.

## Portfolio relationship

GraphRAG Agent is the user-facing flagship. Knowledge Manager is an optional
Git-native/MCP extension. Goal Harness Fullstack provides integration and
delivery evidence. Goal Skill owns intake and confirmation; Harness Engineering
owns layered execution and rollback. Cross-links should explain these roles in
one paragraph and should not require users to understand the governance stack
before running the application.
