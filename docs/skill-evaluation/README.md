# Skill Evaluation Artifacts

## DO_NOT_EDIT Convention

All files under any `outputs/` directory in this subtree are treated as evaluation evidence snapshots.

- DO NOT manually edit `outputs/**` files unless an explicit normalization task is requested and recorded.
- When normalization is required, apply a repository-wide, traceable rule and avoid selective manual rewriting.
- Any non-evidence interpretation, summary, or analysis should be added outside `outputs/` (for example, in benchmark or analysis documents).

Scope for this convention:
- `docs/skill-evaluation/**/outputs/**`

## Reading Order

1. Read [`../superpowers/skill-evaluation.md`](../superpowers/skill-evaluation.md) for the interpretation boundary around evaluation artifacts.
2. Read [`../superpowers/harness-engineering-layer-mapping.md`](../superpowers/harness-engineering-layer-mapping.md) when a benchmark or eval prompt refers to Layer 0-6.
3. Edit benchmark summaries or eval definitions only outside `outputs/` so evidence snapshots remain untouched.
