# Harness Engineering Layer Mapping

This note maps the `harness-engineering` skill's canonical Layer 0-6 model onto the broader `superpowers` documentation set.

## Canonical Sequence

| Layer | Meaning | Main Output |
|-------|---------|-------------|
| 0 | Capability boundary check | Facts about what existing components can and cannot do |
| 1 | Single-component MVP verification | Reproducible component notes and usage constraints |
| 2 | Integration topology and bridge pipelines | Data handoff contracts between components |
| 3 | Domain model and storage shaping | Entity, graph, and persistence decisions |
| 4 | Product and architecture blueprint | PRD, backend API spec, frontend design spec |
| 5 | Project engineering conventions | Repo layout, environment rules, agent workflow, delivery guardrails |
| 6 | Implementation and verification | Production code, tests, review, and acceptance |

## How To Read It In Superpowers

Use the `superpowers` material as execution guidance, but treat Layer 0-6 as the evaluation contract for this skill.

1. Read the eval prompt expectations first to see which layer transition is being tested.
2. Use Layer 0-2 to decide whether the user needs exploration, MVP validation, or bridge design before any product coding.
3. Use Layer 4 before writing features that depend on product scope or API shape.
4. Use Layer 5 before agent coordination or repo scaffolding so implementation follows a stable workflow.
5. Enter Layer 6 only after the earlier artifacts exist or the prompt explicitly states they already exist.

## Boundary Notes

- Layer numbers here are specific to `harness-engineering` eval semantics and should be cited as `Layer 0-6` when writing benchmark commentary.
- `BridgePipeline` belongs to Layer 2 in this eval set because it describes inter-component handoff, not downstream product implementation.
- PRD and API or frontend design artifacts belong to Layer 4; project layout and development conventions belong to Layer 5.
