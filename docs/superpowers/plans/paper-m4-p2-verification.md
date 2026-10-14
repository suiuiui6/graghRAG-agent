# M4-P2 软件验收记录

项目：graphrag-paper-001；日期：2026-10-07；路由：SCI-Skills，不使用 goal。

结论：P2 已实现并通过限定的软件验证；M4 仍 PARTIAL，P3 未执行。当前学术路线的 M2 新颖性复核保持打开，M3/M4 资产仍属暂定；本记录不撤销该状态，也不产出新性能结论。

## 交付与合同核对

| 控制 | 实现/证据 | 状态与边界 |
|---|---|---|
| 稳定身份/来源合并 | evidence_trace.py；跨文档、缺 ID、乱序、内容冲突、长文本 Vector/BM25/rescue 测试 | 软件通过；无 namespace 为 unknown，不冒充 grounding |
| 筛选与重排观测 | retrieval.py；阶段/drop 记录、同分顺序、rerank score、protected 投影测试 | 软件通过；粗粒度阶段原因，不虚构逐对象理由 |
| 可选全文追踪 | models/config/source_control/routes；strict bool、关闭不返回、503测试 | 软件通过；默认关闭不是访问授权 |
| 真实上下文 | prompt_builder.py；混合文本、超长 header、hint、截断及省略号测试 | 软件通过；哈希对应实际消息；token 仍字符估算 |
| 原答与程序修补 | generator.py；真实生成函数、替代 provider 边界成功/失败响应 | 软件通过；未验证真实模型行为/接口 |
| 确定性旁路 | 真实 FastAPI/BM25/SQLite/文件存储端点 | 软件通过；context/raw null，单列 decision evidence |
| 引用身份 | canonical exact match 正例和 legacy substring/空标签反例 | 软件通过；不证明语义支持 |
| API 4000字符截断 | route 独立 api_response_limit 阶段 | 已实现并静态核对；本批无专门超4000字符端点用例 |
| 冻结/盲评/成本 | P3 计划 | 未执行 |

身份冻结在完整观测文本上，非原文真实性背书。原 span 未验证时为 null，content_sha256 与 observed_text_sha256 分别表示投影前内容和阶段文本。unique legacy citation alias 保持兼容，冲突/缺失改用 canonical ID。重复 RRF/rerank 采用最大观测值，score_observations 保留各次观测；不是重新运行重排。

## TDD 与只读复审

先观察身份/context/答案链/端点新增用例失败，再实现；复审发现并以反例修复：Vector 投影前身份缺失、Vector/MQ 旧 ID 去重、rescue 重合并丢实际 rerank、生成省略号被映射为原文、投影丢 protected_evidence、generator storage rescue cap-first。最后 canonical 子串误判反例运行结果为2 failed（预期 RED），修复后 canonical 子集3 passed。保留既有历史 helper，不借它剥离研究身份的文档前缀。

chatbot-reviewer只读核查参与本批；最终复核未发现仍需阻断的Critical/Important问题，确认canonical精确验证与storage rescue修复。报告不作为测试执行证据，189项回归由主会话执行。全部Important修复均按本地反例复现和选定回归确认；未审计全仓库生产安全。

## 实际测试命令与结果

工作目录：backend；解释器：已有 .venv/Scripts/python.exe（Python3.12.8）。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
./.venv/Scripts/python.exe -m pytest tests/test_evidence_trace.py tests/test_source_control.py tests/test_source_control_integration.py tests/test_query_budgeting.py tests/test_hybrid_retrieval_trimming.py tests/test_community_global_mode.py tests/test_retrieval_stage_metrics.py tests/test_retrieval_precision_tuning.py tests/test_tail_latency_controls.py tests/test_query_preprocess_guard.py -q -p no:cacheprovider
```

最终收尾复跑：**189 passed, 2 warnings in 6.13s**，退出码0。构成：P2证据单元30项、P1来源控制29项、本地集成23项、选定已有回归107项。已有警告为 pytest unknown timeout 配置及 jieba/pkg_resources 弃用，不安装依赖消除警告。未运行全仓库测试/漏洞扫描/真实模型集成。

另外用现有解释器对10个新增/修改Python文件执行内存compile（不生成pyc），并用PyYAML解析SCI状态：均通过；git diff --check无错误，仅Git既有LF→CRLF提示。HEAD仍46b202c3e400741fd569f024412c0745f224a538，工作树非冻结。

真实依赖范围：隔离本地 BM25、SQLite、FastAPI、文件存储；Chroma 使用显式 TEST_ONLY 二维向量，不加载 embedding。provider 成功/失败分支仅替代 requests.post 边界，实际 generate_answer/追踪逻辑运行；不是生成模型集成或科学样本。所有夹具不得流入历史 ground_truth/raw_runs。

## 请求级上下文审计（限定范围）

Score：6/10；Stability：constrained。此为请求可观测性与局部控制评价，不是整个 Agent/多租户系统评分。已复现的 Important 缺陷修复后，无已知未修复 P0/P1；P2残余是独立治理工作，不宣称已经验收。

组装链：索引全文 → canonical identity → 分路/救援/融合/预算/重排 → retrieval_final → prompt 实际正文与消息哈希 → provider/确定性旁路 → 答案转换 → API截断。

| 控制 | 状态/证据 | 失败面与后续验收条件 |
|---|---|---|
| 数据/指令边界 | partial；本批不修改系统模板 | 注入防护未专项验证；后续独立攻击用例验证，不能由 trace 推断安全 |
| 身份/来源/转换观测 | implemented；上述测试与 stage ledger | unknown 映射不准许提升到 gold grounding；以核实原文定位后再评分 |
| 硬预算 | partial；字符截断和候选上限已有回归 | 不同 tokenizer 实际 token 超限风险；阈值仍4字符/token估算，后续实测 tokenizer/总预算 |
| 请求隔离 | implemented；P1并发/配置隔离回归 | trace 请求内深拷贝；跨请求持久化、tenant namespace 未审计 |
| 全文最小披露 | partial；默认关闭与端点测试 | 显式开启可能包含敏感正文；现有授权/脱敏/留存规则须独立核验 |
| 生命周期/TTL/压缩/确认 | not assessed | 未新增 session治理；应按专门生命周期合同验证，不纳入P2完成声明 |
| 长任务/冻结复现 | partial；记录消息哈希 | 工作树尚未 freeze；P3须验配置、实际源码哈希、失败分母与预算 |

治理顺序建议为：保留身份与披露边界 → P3预算/冻结 → 独立生命周期/租户授权审计。重评分需要真实模型上下文消费、token预算、原文定位和持久化访问策略的实际证据。SCI-Skills 未因本次软件通过推进到 M5。

## 保留与限制

收尾实测历史ground_truth.json、raw_runs.jsonl、uv.lock哈希分别为95f2fd33af49772c6e5369d8e7ad06b6000999bce0930628ed2891a686dc3867、0a47a175ff6b15cd43e68b26b736add50fb7886e185511e1250e69f9b07b7aca、31caa7407226490b13e1853875eb1ebbe8f895980da39f2b19f58c79f11c14a3，与P1记录一致。不重写草稿、实验和锁文件。仅修改此项目，未读取凭据、联网、下载/安装、提交/推送或改分支。已有未提交资产与M2并行记录保留，不以HEAD冒充工作树冻结。

下一动作：M4-P3 冻结变体运行与离线裁决接口（当前论文新颖性门仍独立保持打开）。
