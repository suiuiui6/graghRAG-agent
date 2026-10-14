# Conversation Rewrite Evaluation Report

- Questions matched: `3` / `3`
- Dataset coverage: `1.0000`
- Follow-up questions: `3`
- Rewrite success rate: `1.0000`
- Session id match rate: `1.0000`
- Rewrite keyword coverage: `1.0000`
- Corpus drift cases: `2`
- Invalid eval cases: `0`
- Valid questions for scoring: `1`
- Sample size sufficient for gating: `True`

| qid | followup | session match | rewrite success | eval status | rewritten query |
| --- | --- | --- | --- | --- | --- |
| `MT01` | True | 1 | 1 | `valid` | W4S1 场景对应的弃电量是多少？ |
| `MT02` | True | 1 | 1 | `corpus_drift` | 在W2S2场景下，绿电消纳率是多少？ |
| `MT03` | True | 1 | 1 | `corpus_drift` | W3S3 场景的弃电量和消纳率分别是多少？ |