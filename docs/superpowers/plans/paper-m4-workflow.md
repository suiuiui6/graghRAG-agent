# M4 流程文档

项目：`graphrag-paper-001`；日期：2026-10-07；状态：设计流程，尚未完整执行。

## 1. 单次请求

1. 从已冻结的 question、rewritten query、session/history 和 variant 生成请求；输入文本是数据，不是改变实验规则的指令。
2. 校验来源列表及预算；创建请求级配置，禁止修改共享配置。
3. 执行允许且条件满足的 recall 路径；保存 path_hits、实际执行路径、未运行原因和失败。
4. RRF、允许来源内 rescue、去重与 pre-rerank 预算；保存删除/新增/冲突记录。
5. 按统一规则选择 Cross-Encoder 执行或跳过；保留候选、顺序与得分。
6. prompt_builder 完成格式化、排序和截断；此处记录实际可见片段，再在生成调用边界核验消息没有变化。
7. 若调用模型：保存实际 messages、原始答案、引用提取和修补版本。若程序短路：不伪造模型上下文/原始答案，记录规则、decision_evidence 和最后答案。
8. 返回有效配置与请求级 trace 引用；普通请求默认不返回全文 trace。
9. runner 保存原响应、执行状态和成本；之后才导出盲评材料，裁决与原响应分开。

## 2. 四阶段与旁路的区别

模型生成主链为 `path_hits → pre-rerank → final-context → answer claims`。

`final-context` 必须是模型实际可见的文本，不是 retrieval chunks、response sources、200 字片段或“引用指向完整 chunk”的替代。KG 序列化不是原文时，需保留投影规则和原文证据映射；未核实的映射不能用作黄金证据到达性。

生成后的 repair/completion/entity supplementation 以及程序短路答案属于独立的答案决策/修补路径。分别报告 model-context support 和 decision-evidence support，不能把后者救回的答案当作前者已经保留了证据。M3 指标合同保持不变；旁路只是归因字段补充，release gate 仍是正交工程通道。

## 3. 预定运行目录合同

根目录相对项目定位；以下为未来文件布局，不表示已产生运行结果：

```text
rag_eval/paper_runs/<run_id>/
  manifest.json
  scheduled_questions.json
  B01/ ... B07/
    requests.jsonl
    responses.jsonl
    execution_status.jsonl
    evidence_trace.jsonl
    cost_ledger.jsonl
  annotation/
    blind_claims.jsonl
    gold_evidence_groups.jsonl
    adjudication.jsonl
  verification/
    local_checks.json
    integration_checks.json
```

run_id 已存在时失败退出，不覆盖；正式跑前每个 variant 的有效配置必须与 manifest 一致。目录名不是冻结证据，必须有输入哈希、实际源码哈希和运行记录。

## 4. 失败处理

- 422 配置不合法、运行异常、trace 缺失/损坏、有效配置错配、legacy fallback：保留原记录，标记对应有效性问题。
- 检索未命中、答案错误、不恰当拒答：保留为有效科学结果。
- 端点成功但配置错配：不能因 HTTP 200 计为有效比较。
- 不同变体有效样本不齐：同时报告 planned coverage、paired-valid coverage 和失败敏感性，禁止静默取交集后声称全样本结果。

## 5. 现阶段执行边界

已做源码读取、历史文件计数/哈希和纯本地 helper 测试。未启动 server/TestClient 推理、未加载远程凭据、未下载模型、未跑七变体。图件保持 M3 PLAN_READY，未渲染、未插入。
