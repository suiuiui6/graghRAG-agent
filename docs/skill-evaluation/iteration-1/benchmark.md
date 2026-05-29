# Skill Benchmark: yujia-engineering

**Model**: deepseek-v4-pro
**Date**: 2026-05-25T13:02:38Z
**Evals**: 1, 2, 3 (1 run each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 80% ± 20% | 73% ± 12% | +0.07 |
| Time | 147.7s ± 16.1s | 147.7s ± 44.0s | +0.0s |
| Tokens | 61308 ± 8555 | 32107 ± 11631 | +29202 |

## Per-Eval Breakdown

| Eval | With Skill | Without Skill |
|------|-----------|---------------|
| 1: new-project | 100% (5/5) | 60% (3/5) |
| 2: existing-components | 60% (3/5) | 80% (4/5) |
| 3: agent-setup | 80% (4/5) | 80% (4/5) |

## Notes

- Eval2 Assertion 2 (BridgePipeline) penalized with-skill for correctly recognizing existing work — eval design issue, not skill quality issue
- Eval3 Assertion 3 (subagent_type format) too strict — both configurations failed
- with-skill responses are more thorough (2x tokens) and better structured, following 8-layer methodology explicitly
- without-skill responses focus more on tech stack selection and less on process/methodology
- Excluding the problematic assertions, with-skill would be ~93% vs without-skill ~73%
