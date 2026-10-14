# 企业知识库入驻清单

> 每次放入新的企业文档进入知识库之前 / 之后，逐项打勾。
> 最后更新：2026-07-04

---

## 放文档之前

- [ ] **确认文档类型**：列出所有要放入的文件类型（PDF 报告 / DOCX 规章 / XLSX 台账 / 邮件 / 合同 / 其他）
- [ ] **提取实体白名单**：从这批文档中人工过一遍，列出你认为必须被检索到的实体类别
  - 人名 / 部门 / 项目编号 / 合同金额 / 日期 / 设备编号 / 物料名称 / ...
- [ ] **提取同义词表**：同一概念在文档中可能有多种叫法，列出来
  - 例："QHSE 管理部" = "质量安全部" = "安环部"
  - 例："吨氨成本" = "合成氨单位成本" = "制氨成本"
- [ ] **补领域词典**：把同义词表写入 `backend/config/domain_dict.yaml`
  - 每个词条需要：`term`, `synonyms`, `abbreviations`, `related`, `entity_type`, `category`, `description`
  - 当前有 70 个词条，每批新文档预期 +20~50 条
- [ ] **补错别字修正表**：列出这批文档中容易打错的关键词
  - 写进 `backend/retrieval.py` 的 `_normalize_query_typos()` 函数
  - 中文形近字："氨"↔"案"、中文同音字："用店"↔"用电"
  - 英文拼写：产品名、软件名、缩写

## 放文档之后

- [ ] **跑一遍 LangExtract 抽取**：检查 KG 构建结果
  - 打开 `output/kg/doc_xxx/nodes.json`，抽样 20 个实体
  - 确认实体类型、label、properties 字段是否正确
  - 特别关注：数字值是否挂到了正确的实体上
- [ ] **跑一遍索引**：确认 BM25 / ChromaDB / Table 索引正常生成
- [ ] **用 5 个真实业务问题手工测试**：
  - 1 个精确事实查证（"XX 项目的合同金额是多少"）
  - 1 个列表型查询（"有哪些部门参与"）
  - 1 个口语化查询（用业务人员常用的非正式说法）
  - 1 个模糊查询（故意打错一个字）
  - 1 个跨文档查询（涉及两个以上的文件）
  - 记录每个问题的答案质量和 citation 准确性
- [ ] **更新 eval ground truth**：
  - 把上面 5 个测试问题 + 正确答案写进 `ground_truth.json`
  - 跑 `run_inference.py` 生成新的 `raw_runs.jsonl`
  - 跑 `metrics_a1_retrieval.py`、`metrics_a2_faithfulness.py` 确认指标不下降

## 度量基线（放文档前后对比）

| 指标 | 放之前 | 放之后 | 警戒线 |
|------|--------|--------|--------|
| keyword_coverage_macro | | | ≥0.70 |
| hallucination_rate | | | ==0.0 |
| forbidden_violation | | | ==0.0 |
| 人工抽检 5 问通过率 | | | 4/5 |

---

## 常见踩坑提醒

1. **PDF 里的表格数据**：MinerU 解析后，表格行可能被拆散成独立 chunk。检查 `output/mineru/` 下的 JSON 内容段是否保留了完整的行结构。
2. **英文缩写混在中文里**：LangExtract 可能把 "Pandas/NLP/MILP" 当成噪音跳过。如果重要，在 domain_dict 里加 `abbreviations` 字段。
3. **数字不挂实体**：报告里出现 "3554 元/吨" 但 KG 里没有对应的 entity。检查 LangExtract 的 metric 抽取规则是否覆盖了这类数值+单位模式。
4. **用户不打全称**：用户会搜 "安环部" 不会搜 "安全管理与环境保护部"。domain_dict 的同义词索引是这个场景的唯一防线。
5. **查询太口语化**：如 "那个绿电项目花了多少钱" → preprocess_query 的 LLM 改写能处理，但如果 LLM 挂了，则依赖 domain_dict 展开。口语化关键词也需要进词典。
