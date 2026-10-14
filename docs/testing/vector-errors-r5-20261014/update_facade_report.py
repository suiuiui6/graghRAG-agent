from pathlib import Path
p=Path('docs/testing/2026-10-14-vector-errors-r5.md');s=p.read_text(encoding="utf-8");s=s.replace('增删改、现役 VectorStore API', 'read/scan 每次最多 10000 条，非全量且未实现分页。增删改、现役 VectorStore API');s=s.replace('- 最终 5 个 unittest', '- 新门面红 2 项 exit 1（score 同向1/正交0/反向-1，超大整数向量裸 OverflowError）；修复为 `round(1-distance/2,4)` 及显式向量校验窄转 invalid_input 后，真实 facade 同向1/正交0.5/反向0、prefilter top1、超大整数拒绝 2 个测试绿 exit 0。原9 cosine只覆盖旧projection消费路径，此新增测试实际经过新门面。\n- 最终 5 个 unittest');p.write_text(s,encoding="utf-8")

