# GraphRAG 历史评估复核：RAG、溯源及评测

日期：2026-10-12。范围：`GraphRAG(1).md` 的 21–35、42–44、55 项；以当前工作区（含未提交变更）为准。只读审查，不读取 .env、不主动执行外部模型。测试结果见下方；测试文件存在仅代表覆盖线索，不等于本次通过。

## 逐项状态

|编号|状态|剩余优先级|当前代码证据与判断|测试证据及不足|
|---|---|---|---|---|
|21|部分修复|P1|`backend/kg_builder.py:116–306` 增加 reports_to、owned_by 等 7 类属性关系；但仍保留结构边，模糊/子串推断没有独立事实证据、时间与限定条件，不能证明业务因果。|本次未见关系事实支持性专项通过记录；需原文标注三元组集。|
|22|未修复|P1|`backend/services/kg_service.py:26–36` 仍是 nx.Graph，同一对节点 add_edge 覆盖关系，且仅保留 relation，edge_id/properties 丢失。|需方向、多边和完整属性往返测试；静态可直接确认。|
|23|未修复|P1|`backend/kg_builder.py:29–43` 每条 extraction 建节点；`backend/services/kg_service.py:59–62` 仅按目录序号加前缀 compose，无跨文档实体对齐。|现有索引测试验证召回，不验证实体消歧；需同名异人和同人别名数据集。|
|24|未修复|P1|`backend/bridge.py:32–42` 仅规范化 item，搜索原始 full_md，前 40 字符命中后仍以完整 normalized 长度给 end。|表格文本测试不覆盖偏移；需换行/多空格/相同前缀冲突回归。|
|25|未修复|P1|`backend/bridge.py:216–245` extract_section_text strip 后 offsets 仍为 sec.char_start。|`test_bridge_table_body.py:23–50` 仅测试无前导空白样本；不能证明偏移修复。|
|26|未修复|P1|`backend/bridge.py:54–68` 未匹配仍造连续 Segment；`backend/grounding.py:59–81` 命中 Segment 即 grounded，没有文本匹配真实性校验。|需不存在文本不得 grounded 的负例；静态确认残留。|
|27|未修复|P1|`backend/schema.py:30–36` 跨块退回首块；`backend/grounding.py:27` 未知文档 offset=0，`schema.py:7–17` bbox 无校验。|需跨页多 span、未知 doc、逆序/越界 bbox 回归。|
|28|部分修复|P1|`backend/bridge.py:76–82,105–115` 已引入 table_body 可检索文本；仍将 HTML 扁平化，未保留单元格 span/表头继承；image/chart 仍主要取 caption（85–98）。|`test_bridge_table_body.py` 验证表格数值进入抽取输入；未覆盖计算、复杂合并单元格与图像证据链。|
|29|部分修复|P1|`backend/kg_builder.py:325–339` 有 schema_version；末尾新增 lineage 记录。但 `worker.py:167` 仍传空 metadata，`kg_builder.py:331–340` 持久节点不含 char_interval/block_type，`schema.py:65–73` KGNode 本身不含它们。|新 evidence_id 的身份校验是局部进步，不能补回原始图节点已丢弃的字符跨度；需从入库到引用端的完整 manifest 回归。|
|30|部分修复|P1|旧入口 `routes/query.py:113–133` 已用索引查找且有严格上限；新 `retrieval.py:1579` indexed_kg_recall、1716 BM25、1832 RRF、1877 rerank 实现混合排序。枚举/统计问题仍需分页/聚合及业务保留集证明。|`test_kg_indexed_recall.py:116,142,158,201` 覆盖索引和限额；不证明列表完整率。|
|31|部分修复|P1|`backend/kg_store.py:201–243` 已从遍历当前父节点读关系，修正旧的二跳直接边退化；有 fanout 截断。但返回扁平 neighbors，无 parent/path、方向、每边证据，无法还原完整推理链。|`test_kg_indexed_recall.py:226` 验证有界遍历；需有序路径及事实边证据测试。|
|32|部分修复|P1|`routes/query.py:118,163–171,219–235` 有结果限额、fanout 和 recursion_limit；`routes/rag_query.py:97–120,306–311` 请求级候选/上下文预算。未见请求预算参数统一控制旧 Agent 调用次数、金额、总截止时间。|`test_query_budgeting.py:13,28,120,131,172,410` 有配置/截断/传递测试，但不等于统一费用/并发/截止时间。|
|33|部分修复|P1|`prompt_builder.py:24–29` 强制句级引用；`generator.py:1243–1292` 验证引用 ID 是否在上下文，有 canonical ID 精确匹配。但不验证引用是否支持句子事实；旧 /query 也没有逐结论校验。|`test_query_budgeting.py:512–878` 有特定拒答/反驳回归，部分直接针对历史 Q41/Q49；需独立攻击集与未见业务保留集，不能据此声称提示注入已消除。|
|34|未修复|P1|`routes/query.py:269–295` 仍对所有 content 为字符串的消息解析 JSON，并从答案 regex 抽 ID；没有 ToolMessage/tool_call_id 检验。旧入口在 `server.py:358` 仍注册。|主 /rag/query 不再走该来源收集，但旧入口残留须单独关闭或修复；需用户 JSON 伪来源负例。|
|35|未修复|P1|`routes/query.py:238,250` async 中直接同步 invoke；主 `routes/rag_query.py:221,306` async 中直接 generator.generate，同样可阻塞事件循环。|需慢模型时并发健康探针和取消测试；静态确认两个入口均残留。|
|42|部分修复|P1|`rag_eval/run_inference.py:149–159,253–310` 已用 TestClient 调真实 /api/v1/rag/query，188–218 保留响应及分阶段召回 IDs。旧自建 Agent 问题已修，但代码/模型/索引/prompt 固定及全套当前在线复验仍不足。|`test_query_budgeting.py:254,309,356` 与 `test_retrieval_stage_metrics.py:44–68` 有响应/排名保留测试；未在本次执行外部模型评测。|
|43|部分修复|P1|`run_inference.py:194–205` 保留有序阶段 IDs，`test_retrieval_stage_metrics.py:44–68` 确认不排序；A2 脚本明确改称 node_id_validity。但 `metrics_a2_faithfulness.py:24–47,154–158` 仍靠 ID/关键词及单字“无”判拒答，未做事实支持和人工校准。|排序失真有回归覆盖；引用合法率不能称零幻觉，拒答混淆矩阵待验证。|
|44|部分修复|P1|新增 `ground_truth_multiturn_smoke.json`；但 `run_inference.py:35–40` 硬编码 D:/graghRAG-agent，`metrics_a2_faithfulness.py:66–70` 绑定特定文档图谱；主报告仍围绕 50 题。未形成 200–500 题分层业务保留集和置信区间。|smoke 集是范围扩展，不能代替泛化证明；需去敏语料/哈希/相对路径可复现包。|
|55|部分修复|P2|主入口 `routes/rag_query.py:315–338` 使用真实 retrieval score；旧 `query.py:296–313` 仍 set 无序、0.9、answer[:4000]、示例 doc ID 及按消息计工具数。主入口 fallback `rag_query.py:273–284` 也静默截断/默认 ID。|预算及分阶段指标测试有改善；需两入口响应真实性、显式截断、引用顺序回归。|

## 优先计划

1. P1：先封闭旧 /query 的伪证据入口，并解决两个 async 查询路由中的同步阻塞；补负例及并发探针。
2. P1：修复 bridge/grounding 坐标真实性（24–27），再补多 span 和从原文件到图节点、答案引用的持久化证据链（29）。
3. P1：保留方向/多关系/边证据（22），建立事实关系与结构关系的显式分层（21），实现可还原路径（31）和实体消歧（23）。
4. P1：统一调用、时间和费用预算；以独立保留集验证混合召回、句级支持、拒答和提示注入，不以历史题目定制通过代替业务泛化。
5. P2：清理旧入口响应语义，统一真实分数、真实文档标识、引用顺序及截断提示。

## 验证范围

执行测试时设置 `PYTHON_DOTENV_DISABLED=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`，使用 backend/.venv；未运行 provider 模型评测。见后续测试结果补充。历史 release gate 的失败仅为历史证据，不代表当前线上结果。

本次完成的命令（backend 目录）：`.venv/Scripts/python.exe -m pytest tests/test_retrieval_stage_metrics.py tests/test_eval_keyword_normalization.py -q --disable-warnings -p no:cacheprovider`。结果：**8 passed, 1 warning in 3.44s**。覆盖阶段 ID 的真实顺序、去重、节点投影及评测关键词规范化；属于本地单元回归，不是外部依赖集成证明。

两个扩大测试集合运行出现长时间无输出，均中止，不能计入通过：首次包含 bridge_table_body、query_budgeting、kg_indexed_recall、retrieval_stage_metrics、eval_keyword_normalization；第二次移除 query_budgeting 后仍未完成。仅观察到进度点，不将其转换为测试通过数，也不将挂起直接归因为产品缺陷。

