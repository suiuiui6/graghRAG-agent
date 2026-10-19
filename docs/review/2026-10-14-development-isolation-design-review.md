# 公开开发隔离与 P0/A 预算：独立设计审查

日期：2026-10-14（Asia/Shanghai）。审查者：独立 dev_review Agent。按 requesting-code-review 技能适配设计审查，只读源代码与设计输入；未读 .env、未联网、未调用模型、未写入索引。

## 审查总结

**复核：结构适配设计 PASS，可进入独立模块编码；SDK 路径设计 D1 已修订关闭，2 项 Medium 纳入实现验收。无 Critical。** 首次输入发现 1 项 High 的 SDK 设置传递陷阱，以下保留其依据。三臂身份、Gold 隔离、未知成本不归零及工程不可用不证明科研缺口的边界清楚。远程执行仍须后续代码与离线 guard 行为审查，不由设计 PASS 自动放行。

本结论仅为设计审查，不是代码通过、远程预算完成或产品整体验收。

## 问题清单

### 🟠 High D1：SDK 超时、重试和并发必须落实到真正的客户端

- 位置：`docs/contracts/2026-10-14-development-isolation-adapters.md:31–33`；`langextract/langextract/providers/openai.py:106–169,226–227,294–305`；`langextract/langextract/extraction.py:247–260,282–302`。
- 问题：契约要求 timeout=30/max_retries=0，但本地 OpenAI provider 的构造器仅将 api_key/base_url/organization 传入 OpenAI。将 timeout/max_retries 放进 provider_kwargs 会被保存为生成参数，无法设置 SDK。worker 使用 config 分支，extract(language_model_params=...) 分支不运行；仅在 lx.extract 上配置 max_workers=1 也不能证明 provider 自身的线程池是 1。默认 SDK 重试会使尝试和时间上限失真。
- 建议：隔离研究 factory 创建模型后，在 SDK 层用 `client.with_options(timeout=30, max_retries=0)`（或等效构造替换）落实；max_output_tokens=4096 与 max_workers=1 进入实际 provider 构造参数，annotator 也设 max_workers=1。不修改原入库提示或全局生产 provider。离线测试应检查最终 client 配置、最终 payload 的 max_tokens=4096、SDK 层一次失败只有一次传输；实际 transport 继续为全部尝试保留硬 guard。
- Before（不能证明生效）：

```python
ModelConfig(provider_kwargs={"timeout": 30, "max_retries": 0})
lx.extract(config=config, language_model_params={"max_output_tokens": 4096})
```

- After（研究 factory 示意，需对实际安装版本验证）：

```python
provider_kwargs.update(max_output_tokens=4096, max_workers=1)
model = create_model(config=bounded_config, use_schema_constraints=False,
                     fence_output=True)
model._client = model._client.with_options(timeout=30, max_retries=0)
# 使用同一个受限 model；或仅在隔离副本工厂中返回它。
```

### 🟡 Medium D2：editable LangExtract 也属于执行源码快照

- 位置：契约第 25 行、计划第 4 步；`backend/pyproject.toml:65`、`backend/uv.lock:1247–1249`。
- 问题：LangExtract 是 ../langextract editable 源，单独复制 backend 并记录软件锁不足以绑定实际加载的 provider/extraction/annotation 源码；backend/pipeline.py 还会自行插入相邻 langextract 路径。
- 建议：复制需要的 LangExtract Python 源进入同一独占运行根，或者明确只读共享、记录实际 `__file__` 与有效模块全体 hash，并在前后复核。一致性不满足则停止，不能依赖 lock 代替 editable 源 hash。
- Before：仅记录 backend 副本和 uv.lock。
- After：记录 backend + 有效 LangExtract 源快照、实际模块位置和依赖版本；证明无生产路径写入。

### 🟡 Medium D3：原生 best-effort grounding 与精确字符证据必须分开

- 位置：契约第 27 行；`backend/schema.py:32–40`、`backend/grounding.py:58–95`。
- 问题：PositionMap.lookup_range 在无法整段包含时退回起点所在 segment，原生 grounded 状态不保证全文 interval 被同一块覆盖，更不保证 extraction_text 与源 slice 逐字相等。
- 建议：保留原生状态以忠实执行 P0，另存 source_slice、区间有效性、alignment、exact_text_match、跨块状态；证据支持评分只能使用实际输入及原文核实结果，不能把 grounded 标签直接算精确支持。HTML bbox/page 缺失保持 None，不造 PDF 坐标。
- Before：`grounded == evidence_supported`。
- After：`native_grounding_status` 与 `source_interval_valid / exact_text_match / evidence_support` 分列。

## 修订复核

当前契约 SHA256 `d03b1d1b791129185ef6413456106a2de560cca5b826d64bb19191d3b2b2d72b` 明确 `provider_kwargs.max_output_tokens`、最终 `_extra_kwargs`/HTTP payload 校验及 SDK `_client.with_options(timeout=30,max_retries=0)`，D1 的配置传递设计阻断关闭。thinking 通过 SDK create extra_body 展开后由 transport 验证顶层 disabled，不满足 NOT_SENT，方向可执行。未自行联网核查 flash 默认 thinking 声明，仅审查本地实现接口可承载此显式请求。

实现还须同时限制 provider 的 max_workers=1 与 annotator 的 max_workers=1；失败后的 guard 关闭优先于原生自动重试。D2/D3 是清楚可独立落实的验收事项，不阻塞结构模块编码。设计通过不表示 provider 包装或收据已实际验证。

## 已核实成立的边界

- `rag_query` 在显式 document_id 时进入 `_generate_scoped_rag`；授权图仅保留 grounded 节点，KG-only，禁止 multi_query/cross_encoder，最终 answer[:4000]。管理员 request.state fixture 只支持研究函数级调用，不证明 JWT 或 HTTP 验收。
- worker `_run_langextract` 的企业实体 prompt、真实 few-shot、3000 字符分段和 200 字符上下文可复用。canonical 桥接不是原 MinerU 或 DOCX/XLSX 原生解析；报告应保持这一标签。
- 64 = 24 + 18 + 22。180224 = 24×4096 + 40×2048 是保守最大声明输出；P0 预处理的 300 被 2048 包络，不能报告为实际 usage。每题 P0 一次预处理与最多两次生成对应至多 3 次；失败后 guard 关闭可保留原生重试行为而阻止再次发送。
- 1,200,000 UTF8 bytes 是提示负载安全上限，不能改称真实 tokenizer 或 token 上限。HTTP usage 才能提供本次实测；无 usage 的已发送请求保持成本 UNKNOWN。
- 范围规则以原始标题、XPath/font 与 canonical 证据为输入，禁止 Gold。单章节含子节、连续同父区间和弃权条件属于普通格式适配；不得由六题通路证明泛化。

## 优化建议汇总与关闭条件

1. 先明确 SDK 层配置机制并补离线行为测试，关闭 D1 后再发远程请求。
2. 将 editable 源快照和有效 import 位置纳入离线准备验收，落实 D2。
3. 将原生 grounding 与严格 interval/source-slice 校验列分开，落实 D3。
4. 代码完成后独立复审 guard 并发保留、异常保密、HTTP/SDK 双路径、所有副作用路径及实际请求/响应 SHA；运行后单独审收据。未满足三臂可运行和 usage 闭合前保持“未测齐”。

## 审查输入 SHA256

| 输入 | SHA256 |
|---|---|
| 契约 v1 | 83ad526eed7c1ed442ac055a108a102087a9f4c3375a5ad61731d7804fcf1ea4 |
| 计划 | 4d26646573477cdca9628b426b95eb8c44f0fa38d55f04850b940f7eeb56927c |
| backend/worker.py | 30472444cfe062c02aa2a685615fdbcdbb7f9ebdda27b76cedf08c11ec99a586 |
| backend/routes/rag_query.py | d74e27e9ad4b33b355927d4658060cfdd140dd05ad168f82f3016c1de5966848 |
| langextract/langextract/providers/openai.py | 79547098b45d6981c0a77ce00afd4605aea15aef4618ebdffaec9c57d5b2fde6 |
| langextract/langextract/extraction.py | a4a0995fdc6135d1f9b362fa42c7b5233a81316bcbeF61661571c25929282f7c |

验证：实际 PowerShell 只读 Get-Content/rg/Get-FileHash；关键文件读取与 hash 命令退出码 0。早期候选路径 backend/langextract_pipeline.py 与 venv site-packages langextract 不存在，已改查实际本地 editable 源。未执行实验或测试。
