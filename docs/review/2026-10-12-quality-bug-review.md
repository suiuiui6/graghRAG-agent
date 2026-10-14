# 2026-10-12 四项缺陷及行为补测独立复审

## 审查总结

本轮四处生产修复符合局部契约，新增测试有业务结果、异常原因和预算边界断言，独立专项运行通过；接受本轮局部修复。**新增问题：Critical 0 / High 0 / Medium 0 / Low 0；既有整体交付阻塞继续保留，不能据此提交或宣称双覆盖/安全门槛达标。**

输入：根 AGENTS、memory 索引及当日记录、整改计划、既有 quality-remediation-review、三份 CLI/worker/query 专项报告、mapping-red/green 原始日志。复用 requesting-code-review 的独立上下文审查组织方式；using-superpowers 对派发子代理明确允许跳过启动流程。分支 master，HEAD `46b202c3e400741fd569f024412c0745f224a538`；工作树有其他任务大量改动，唯一编辑文件为本报告。无外部模型评审，不修改生产、测试、覆盖配置或 memory。

## 修复与测试审查

| 文件及范围 | 修前行为 | 当前行为与独立判断 |
|---|---|---|
| `backend/doc_processor.py` 670–678 | 合法 JSON 顶层 list/string/number/null 进入 `.items()`，抛 AttributeError | 增加 `if not isinstance(data, dict): return {}`，与既有 docstring 的无效文件返回空映射契约一致；不扩大异常捕获，也不改变字典字符串值过滤。5 个类型回归均有明确 `{}` 断言。 |
| `backend/run_evaluation.py` 258–263 | 空 queries 聚合除零 | 在任何评测之前显式 ValueError，保留非空评分/聚合算法；测试校验异常类型与明确输入错误信息。 |
| `backend/errors.py` 220–229、246–315 | requests 的 OSError 子类先被通用连接分支吞掉；httpx Pool/WriteTimeout 漏识别 | stdlib-only 的 MRO 检查识别 requests/httpx 超时；具体解析异常、HTTP 状态早于通用 OSError，body_code 仍最优先。真实 requests Timeout/ReadTimeout/ConnectTimeout/HTTPError/JSONDecodeError 类及 httpx Pool/WriteTimeout、业务码优先、未知 OSError 回退均有断言。未改错误枚举/wire 字段。 |
| `backend/self_correction.py` 62–95 | 最后一次生成和零预算初始答案未验证便失败返回 | 多一个纯验证轮，预算耗尽在生成之前退出；正常返回轮数等于已完成生成数，生成器最多调用 max_rounds。末轮成功、零预算正确/错误、持续错误2次上限、生成异常一次即停止均有行为断言；符合蓝图 §3.3 新增轮次契约。 |

四份生产文件相对 HEAD 的 diff 仅包含上述修复。生成异常提前结束时仍返回 max_rounds、警告仍显示预算轮数是既有行为，本轮没有引入；本报告不把该返回值宣称为异常场景的实际完成次数。引用标记/数字/转折词规则仍是启发式检查，测试没有声称证明语义事实正确。

新增测试质量与副作用边界：

- KG 测试核对关系类型、目标类型/缺失目标、多值目标、页码/窗口边界、真实中文 JSON 往返及摘要日志计数，摘要 Low 已被有效 capture_logs 断言关闭。
- doc_processor 用真实 DOCX/XLSX/Markdown 和临时磁盘验证表结构、偏移、项目元数据、分块/去重、损坏文档继续处理；mapping 原始红日志为5个 AttributeError 失败，绿日志16通过。这里是独立读取历史日志，未重新执行修前版本。
- CLI 使用真实 main/argparse、MinerU V1 夹具、字符定位、真实公共数据类型和 JSONL/KG 落盘；系统 curl/unzip、模型/向量库边界明确用替身。不是供应商或系统 unzip 集成验收。
- worker 验证分批部分/全部失败、第一根因、图节点边去重、落盘引用、任务路径、附件表归一化和可选增强降级；worker 的 `__file__`、上传目录重定向到 tmp_path，事件/审计与 index setter 替身避免真实 runtime 写入。正常分支 BM25/内存表构建保留真实实现。
- query 验证词项限制、历史裁剪、模型失败的启发式降级、自修正生成预算、真实评测聚合与临时报告。旧 Agent 演示仅将两个明确 KG 读取路径定向临时 JSON，模型构造/agent 创建替身；这是本地 NetworkX 工具行为，未验证实际 agent 循环。
- 六份测试未删除旧断言、跳过失败、增加 coverage 豁免或改写冻结。已读取固定 coverage 配置，仍包含完整 backend source、namespace discovery，默认排除/partial 豁免清空；测试与生成产物排除保持既有定义。此次未重新核对最终全量文件清单/计数，不将专项作为分母或全量证据。

从路径重定向、临时文件和边界替身检查未发现真实 output 写入路径。本 reviewer 没有运行前后对整个真实 output 做完整哈希，因此不把静态隔离判断扩大为全目录独立无变化证明。

## 问题清单（沿用既有交付阻塞）

### 🟠 High：剩余供应链漏洞继续保留

定位：`backend/uv.lock` 的 chromadb 条目及 `frontend/pnpm-lock.yaml` 的既有 advisory 命中条目；具体发现、风险条件及扫描来源见 [既有评审](2026-10-12-quality-remediation-review.md)。本轮四项业务修复不关闭这些发现，本 reviewer 未在线复扫，也未独立证明全部可利用。

建议优先完成有证据的兼容迁移/可达性判断，保留原始报告和非零 gate。Before：局部行为通过后称“安全整改完成”；After：分别记录局部修复通过、剩余 advisory 和提交门槛 BLOCKED。

### 🟡 Medium：新锁环境与镜像兼容性尚无本次独立验证

定位：`backend/uv.lock` 与实际运行环境、`Dockerfile.backend` / `Dockerfile.frontend`。本次运行的是旧 backend/.venv，不使用仍下载中的 `.tmp/backend-quality-venv-20261012`，不能证明升级后 installed==locked 或兼容性。

此前部署/CI锁消费静态 High、图摘要 Low 已关闭，不重开。Node22.23.3 frozen install/build exit0、Docker daemon 不可用是协调者交接状态，本 reviewer 未独立运行，不写成自身实测。Before：旧环境行为通过代替锁升级兼容；After：新锁环境就绪后独立核对版本闭包并回归；容器能力恢复后验证镜像构建。

## 独立实际执行

2026-10-12 19:35–19:36 +08:00，在仓库根执行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_kg_builder_behaviors.py backend/tests/test_doc_processor_behaviors.py backend/tests/test_pipeline_cli_behaviors.py backend/tests/test_evaluation_cli_behaviors.py backend/tests/test_worker_quality_behaviors.py backend/tests/test_query_quality_behaviors.py backend/tests/test_errors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-quality-bugs-20261012
```

**exit 0，261 passed，10 warnings，21.67s。** 告警为 timeout 配置未知1条、jieba/pkg_resources弃用1条、旧 Agent docstring无效转义8条。未把缺失插件的 timeout 约束称为生效。原始输出保留于本 reviewer 工具记录；未额外改写他人日志。另执行四生产文件 `git diff --check`，exit0。

未读 .env，未调模型/真实供应商，未运行 API/全量/覆盖/网络扫描/容器，未申请或绕过升级权限。本专项不涉及 API socketpair 限制。未 git add/commit/push；全量冻结失败及双覆盖提交门槛仍由协调者统一核验。

验证后读取的 SHA256（运行后快照，未声称有运行前后全仓一致性证明）：

| 文件 | SHA256 |
|---|---|
| backend/doc_processor.py | 0e9ccc941b101a5eb225aa40f0b596a3c6435cdc43c8ccc6ba4a0dd9dbfc654d |
| backend/run_evaluation.py | 9fe27b91f5fd9ce0ef44e583a29100a32845d96a6d3fa6234a3681277bb2b1e4 |
| backend/errors.py | 14dd69791988464970382a2b96ff432ed10d968e41e0acbbf79b621b319e4168 |
| backend/self_correction.py | ba6f77675fb9daacec78258120f57cdefa4147ed59511aa5f979ba1a9940b976 |
| backend/tests/test_kg_builder_behaviors.py | 6cd674c7c65b656ae0d92f706cd415c945768834f9dbbb83f755bd50fabbba89 |
| backend/tests/test_doc_processor_behaviors.py | 140dfe4bf32ca830e2dbbf0b5440886e775a19ddce236095550cd7e2faefeaef |
| backend/tests/test_pipeline_cli_behaviors.py | 9d574e7f6127cc472508aabfe9c6a75317d1dac38b1f8dec5bf0c3924ecd2183 |
| backend/tests/test_evaluation_cli_behaviors.py | f811b1961d03de51a093daae252e4d025ac34ce1038ed7461aae6493bd64ae66 |
| backend/tests/test_worker_quality_behaviors.py | 862a6166c60c2d4834cfd9ba9b87a19d94b0118e78425f3912b25b7e00cd920d |
| backend/tests/test_query_quality_behaviors.py | 78f6406f87e9448b6f67e239441e674e16235526ca07dcbcc435f337c8ad636b |
| docs/testing/coverage-backend-2026-10-12.ini | 4d9cc425396c80c16fe2e65efb4786e38f99b305d24f9f7a713fa8fa82922a70 |

## 优化建议汇总

1. 保留剩余漏洞 High；完成新锁环境版本一致性和兼容回归，明确镜像未验收边界。
2. 在最终代码快照上运行规定全量测试与固定全生产分母覆盖，保留原始行/分支计数；冻结失败和任一指标不足90%时禁止提交。
3. 由主协调者将本报告、实际专项结果及剩余阻塞回流统一 memory；本子任务不写共享 memory。

## 同日追加：Lineage 两项测试及词典/图谱/桥接三项修复

协调者在首轮专项完成后追加范围：`test_kg_builder_behaviors.py` 两项 lineage 测试，及 domain_dict/kg_store/bridge 三函数和两份新增行为测试。独立重读当前源码 diff、测试与 [domain-kg 专项报告](../testing/2026-10-12-domain-kg-behaviors.md)。**该追加范围未发现新增 Critical/High/Medium/Low；接受局部改动，既有交付阻塞不变。**

| 定位 | Before | After / 审查判断 |
|---|---|---|
| `backend/domain_dict.py` 262–269 | 仅 lower 查询，含大写的候选字段可能永不匹配 | term/synonym/abbreviation/description 统一 lower 比较，不改返回原始值、CRUD或排序。实际四字段参数化断言覆盖 ASCII 大小写。 |
| `backend/kg_store.py` 444–448 | 原始空端点先加非空 prefix，NetworkX 建立 `doc:` 虚构节点；None 还可能拼接失败 | 原始 src/tgt 非空后才加 prefix；空字符串、None、缺单端和空字典不产生边/虚构节点，有效 legacy包装/prefix 边属性往返仍验证。此次不宣称新增严格端点存在性/类型schema校验。 |
| `backend/bridge.py` 245–246 | strip 后的 Document 起点仍是未去前导空白的 section 起点，grounding 偏移 | 在原始起点加 `len(raw_text)-len(raw_text.lstrip())`，与当前 extract_section_text 的 strip 一致；尾空白不移动起点，Unicode全角空格/tab同样核验，纯空白不建 Document。 |

Lineage 补测使用真实 `LineageStore(tmp_path / 'lineage')` 持久化，再创建新实例读取，明确校验 document parent、doc_id、page_idx、bbox_norm 与 document trace 总数；可选 getter 注入 OSError 后，仍读取真实 nodes/edges JSON 校验保留产物。`kg_builder.py` 未改变；两项 getter 均 monkeypatch 隔离，原有无 document_id 的序列化用例不触发 lineage 默认 store。没有真实 output 副作用路径或放宽原断言。

独立执行如下专项（同前三个离线环境变量及 UTF-8设置，旧 backend venv）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_kg_builder_behaviors.py backend/tests/test_domain_dictionary_behaviors.py backend/tests/test_kg_store_quality_behaviors.py backend/tests/test_pipeline_cli_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-quality-domain-20261012
```

**exit0，122 passed、1 warning，3.00s**；warning 为 timeout 配置未知。包含原先已运行的 KG/CLI 项，因此不与261相加为唯一测试数。没有重跑全量或覆盖，也没有在半成品新锁环境验证。domain-kg 作者红测历史是读取报告所得，本 reviewer 未复跑修前源码。

追加运行后 SHA256：

| 文件 | SHA256 |
|---|---|
| backend/domain_dict.py | 07390519368bb5abbe2280a611eb3eac34da03c34d4bb8314528e82b9e484e18 |
| backend/kg_store.py | ffc075d6649f3a9fb3cd8a2e128a1031d241644db5e2ea08c86729883662ec7a |
| backend/bridge.py | 08a5ac7dce4dac38b33d6f83d38bcabe14c47c47ec2be4b138375a2341314531 |
| backend/tests/test_kg_builder_behaviors.py | 95cbc2708f1b4b9ed7d9f99805d717614a7f88804d154e3c536101599c2015ea |
| backend/tests/test_domain_dictionary_behaviors.py | 874ee3b387a52d607800fb136b92c0c73d13abe7acc47a4ffa33304945a34144 |
| backend/tests/test_kg_store_quality_behaviors.py | e5ac7c0cccfef500c299b2234e71196e12a88565e927847008b72da6729348a7 |

此处 KG 测试快照取代首轮该文件快照（新增两项之后），不修改首轮261结果的历史输入记录。追加三生产文件 diff 保持最小；其他旧修改不纳入本次批准、不回退。
