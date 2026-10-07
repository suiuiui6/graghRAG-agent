# M4 实施计划

项目：`graphrag-paper-001`；复核日期：2026-10-07。
状态：`P1_SOFTWARE_VERIFIED / P2_P3_PENDING`。P1 已实施，软件验证见 `paper-m4-p1-verification.md`；不是整个原型建成或新实验完成。

## 1. 输入与范围

复用已通过的 M3 方法合同、评价合同与七变体计划。目标是让同一生产接口产生可审计、可配对的证据记录，不另造一条“论文专用”检索链。

仅处理 `backend/`、`iteration-2/eval-2-existing-components/rag_eval/` 及对应项目规范和论文记录。不更换核心组件、不改前端、不重建索引、不删除旧草稿或历史结果、不修改全局技能和其他项目。本轮按作者要求使用 SCI-Skills，不启用 goal。

## 2. 已核实的实现缺口

| 落点 | 当前事实 | 对验证的影响 |
|---|---|---|
| `backend/models.py::QueryOptions` | 无来源允许列表；配额必须为 1–50 | 不能用配额 0 表示禁用，也不能通过漏填来源实现消融 |
| `backend/routes/rag_query.py::_build_retrieval_config` | 默认配额合并请求配额 | 当前配置不能执行七变体的来源隔离 |
| `backend/retrieval.py::retrieve` | 正常、global 回退及三类 rescue 分别取证 | 单独修改正常召回不足以阻止禁用来源补入 |
| `backend/retrieval.py::rrf_fusion` | 同 ID 后写覆盖，缺 ID 用 UUID，同分无稳定二级键 | 顺序与来源归因不能保证确定性 |
| `backend/prompt_builder.py::build_prompt` | 再排序、再配额、字符预算截断；metadata 主要为估算 token 数 | retrieval final IDs 不等于实际序列化的可见证据 |
| `backend/generator.py::generate` | KG 补证、storage rescue、确定性纠错/拒答和回答修补 | 有些答案不是只由模型可见上下文产生；raw answer 未作为响应证据保存 |
| `rag_eval/run_inference_helpers.py` | `d0_n0010` 等前缀被移除 | 跨文档同名 ID 会合并；旧 helper 不能成为新 canonical registry |
| `rag_eval/run_inference.py` | 已走生产接口，但执行时要求远程服务凭据 | SCI-Skills 本轮不能启动这条推理实验链 |

上表保留 P1 实施前的缺口快照；来源允许列表与统一隔离现已补齐，其余 P2/P3 缺口仍在。它不是新论文实验结果。

## 3. 分批实施与验收顺序

### P1：请求级来源控制和有效配置

1. 同步 `integration/backend-api-architecture-v1.0.md` 和 `RAG-EVAL-SPECIFICATION.md`，明确新增字段与默认兼容规则，再实现代码。
2. 为 QueryOptions 与 RetrievalConfig 增加显式 `enabled_sources`。省略保持现有默认行为；显式空列表拒绝；未知值拒绝；重复值规范化。保留 `per_source_caps` 作为数量预算，不借它禁用来源。
3. 请求级配置必须覆盖 normal/global/global-fallback/retrieval-rescue/generator-rescue。Multi-Query 必须同时满足其开关、允许列表和依赖来源约束。global/community 属 KG 扩展能力，无 KG 不得调用，记录跳过原因。
4. 禁用来源应在调用前拦截，而非仅在最终结果中过滤。禁用 vector/multi-query 时不得为这些路径执行不必要的 embedding。来源缺失与零命中分开记录。
5. 返回 `effective_config`：requested/allowed/executed/skipped、各阶段候选预算、条件触发、Cross-Encoder 实际执行与跳过原因。
6. 明确“未设置 mask”保持旧兼容；“显式设置 mask”的请求如不能进入主链，应返回明确错误，不得悄悄执行 legacy Agent。

验收：B01/B02/B03 等列表能控制全部取证入口；并行请求不修改共享 pipeline.config；默认请求兼容；真实依赖端点集成测试有记录。此批不宣布预算公平性已完成。

### P2：稳定证据与上下文观测

1. canonical evidence ID 保留文档命名空间；原 ID 仅作映射字段。身份来源按文档哈希、source item/span、原 ID 和对象类型定义版本，不以随机 UUID 作为最终研究标识。
2. 同位置多路命中合并 `source_paths` 与 provenance；同原 ID 不同文档必须分开。同 ID 内容冲突保留冲突记录，不能 last-writer 覆盖。
3. 使用固定来源顺序与稳定排序二级键；记录原 score、RRF score、重排 score、选择/删除/救援原因。
4. 在 prompt 完成格式化与截断后，保存真正的 messages、context 文本/哈希、可见证据片段及原文映射。无法核实原 span 时保留 null，禁止补造 offset/bbox。
5. 模型生成、确定性拒答、确定性纠错分开标记。确定性路径未调用模型时 `serialized_model_context=null`，另存程序使用的 `decision_evidence`；不能把救援证据冒充“模型看过”。
6. 保留 `raw_model_answer`、每次修补阶段及最终答案。未调用模型的路径 raw 值为 null，不复制最终答案充数。

验收：异步返回乱序不改变身份和同分顺序；跨文档无 ID 合并；可见 span 不超出实际截断文本；短路答案完整记录自己的决策证据。追踪为请求级可选，普通响应不默认泄露全文。

### P3：独立变体入口与离线裁决接口

1. 相对路径定位项目；运行目录采用新 `run_id/variant_id/`，已存在目录拒绝覆盖。历史 `raw_runs.jsonl` 原样保留。
2. manifest 记录 Git HEAD 与实际工作树文件哈希、dirty 状态、输入/索引/prompt/model/锁文件版本及有效预算，不能用 HEAD 冒充未提交修改后的源码版本。
3. 从 M3 YAML 生成每个请求并比对 effective_config；冻结前的 null budget 必须阻止正式比较，不能填一个猜测值。
4. 全量 scheduled qids 与成功/失败/配置无效/legacy fallback 分开留档。真实未命中和错误答案保留为有效科学结果。
5. 导出人工标注接口：所有 claim（含无引文）、关联证据、fully/partially/unsupported/contradicted、answer/refuse/correct/clarify/mixed；标注视图隐藏 variant，离线裁决不改原答案。
6. 成本拆分 preprocessing/embedding/retrieval/rerank/generation/repair；缺失记 null/unknown，不默认 0。运行时 token 与字符估算分开。

验收：配置错配可被识别；失败不会消失；输出不会覆盖；零 claim 拒答的支持率为 NA；七变体使用同一生产接口和同一裁决合同。

## 4. 资源需求与备选方案

已核实：后端项目 `.venv` 可运行 Python 3.12.8；PyYAML 已有；`backend/uv.lock` 已有；本地原评测 JSON/JSONL 可读取。R 不可用，但当前不需要 R。PDF 渲染器存在，LibreOffice 不存在；不据此声称能渲染 DOCX。

待核实：本地 embedding/CE 权重能否在禁止下载条件下加载、可供真实集成测试的隔离索引、本地生成模型及作者选择、语料许可和 held-out 划分。原始模型端点信息只在代码中核查，没有读出凭据、配置新服务或发送请求。

备选方案：

- 无本地模型：先完成静态合同、纯本地逻辑验证和标注导出；端点真实集成与推理实验保留 NOT_EXECUTED，不能拿 mock 通过冒充。
- provenance 不完整：记录 unknown/conflict，不报告精准 grounding/bbox 或全文忠实性优势。
- 七变体预算未锁：仅做准备与 development 调试；禁止把调试输出升级为 headline results。
- 历史 50 题已反复调优：用于开发回归，不伪装成未见测试集；M5 再核验 held-out/跨文档证据。

## 5. 当前评审

实施步骤、功能清单、流程和测试准备已有可执行合同；P1 来源控制已实现并通过软件验证，P2/P3 未实现。M4 **部分通过，暂不进入 M5**。

剩余关键缺口：P2 可见证据/决策证据及答案版本追踪；P3 冻结运行、预算锁定与模型完整集成验证。P1 本地真实依赖集成的范围仅 BM25/缓存/确定性回答链。

本轮没有制作新流程图。复用 M3 文字方案作为候选，既有图位/拆图批准仍待作者确认，不擅自渲染或插入。
