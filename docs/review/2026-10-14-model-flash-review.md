# deepseek-flash active 默认迁移独立审查

2026-10-14；审查范围为 10 个 active 文件、模型专项测试及两份缓存 fixture。未读取 .env，未启动生产，未请求远程 API；他人源码修改全部保留。

## 审查总结

**REPAIR：1 项 High，0 Critical，1 项 Low。** requests 顶层 thinking、LangChain extra_body、调用时环境解析、显式参数优先和模型缓存分区符合预期。独立执行 8 项新测试通过，并以真实已安装 LangChain/OpenAI/httpx.MockTransport 验证 SDK 实际序列化，1 次本地模拟传输成功。原生 LangExtract 入库仍未随模型迁移显式关闭 thinking，需修复后再称 active 默认兼容完成。

## 问题清单

### 🟠 High F1：worker/pipeline 的 flash 抽取没有显式非思考配置

- 位置：`backend/worker.py:1182–1189`，`backend/pipeline.py:255–263`。
- 问题：两处 ModelConfig 只改 model_id，provider_kwargs 仍只有 key/base_url。requests 与 LangChain 已显式 disabled，但 LangExtract 没有相应字段。按主审已核实的 flash 供应商能力，默认 thinking 变化会改变抽取输出、资源和旧路径行为；研究隔离 factory 的修补不覆盖普通生产入库入口。
- 建议：在两个 active ModelConfig 中仅对 flash/v4 增加受本地 provider 白名单支持的 `reasoning_effort='none'`，其他模型不传；以真实 provider + OpenAI SDK + httpx.MockTransport 验证最终请求体，不能仅 AST 工厂假对象测试。此审查未联网独立核验该供应商字段语义，依据主审已提供的官方能力核验；代码确实支持该字段透传（providers/openai.py 参数白名单与 infer 白名单）。
- Before：

```python
provider_kwargs={"api_key": key, "base_url": base_url}
```

- After（示意）：

```python
provider_kwargs={"api_key": key, "base_url": base_url,
                 **({"reasoning_effort": "none"} if non_thinking_options(model_id) else {})}
```

### 🟢 Low F2：generator 模块说明仍只描述 v4-pro

- 位置：`backend/generator.py:3–6`。
- 问题：模块注释只说 v4-pro disable，而实际也处理 flash。影响维护理解，不阻断运行。
- 建议：同步描述 flash/v4 显式 non-thinking。
- Before：`Disables thinking mode for deepseek-v4-pro`。
- After：`Disables thinking mode explicitly for DeepSeek flash/v4 requests`。

## 验证记录与限制

1. PowerShell 静态 diff 与明确路径源码读取；退出码 0（早期 services/bot* 路径 glob 在 rg 下不适用，随后定位实际 bot_handler.py）。两旧测试 fixture 只显式设置新模型及缓存键、修正顶层 thinking 断言，没有弱化行为断言。
2. 在 backend 既有 .venv 下 `python -B -X utf8 -`，进程内 socket.connect/connect_ex 只准 loopback，再执行 `pytest.main(['tests/test_generation_model_selection.py','-q','-p','no:cacheprovider','--basetemp','../.tmp/model-review-20261014'])`：退出码 0，**8 passed**；pytest timeout 配置未识别 warning 1，故没有声称插件超时机械门禁。
3. 独立脚本使用假 key/example.invalid，socket.connect 全拒绝，构造真实 ChatOpenAI + httpx.Client(MockTransport)，调用 invoke，验证实际请求 model=flash、thinking 顶层 disabled、无 extra_body 嵌套、响应 content=ok、attempts=1：退出码 0，**REAL_LANGCHAIN_OPENAI_HTTPX_MOCK_SERIALIZATION PASS**。出现已安装 LangChain 自定义 transport 警告，但断言确认 MockTransport 收到 1 次请求；没有远程连接。
4. 不将 parent/coder 自报的 151 专项当作独立执行；本审查没跑产品全量、真实依赖 HTTP 验收、覆盖或漏洞扫描，不提供提交门槛证明。

## 优化建议汇总

1. 修复 F1，两 active 原生抽取入口均覆盖真实 provider/SDK 序列化测试，再独立定点复核。
2. 同步 F2 注释。
3. 隔离预算 runner 仍须专门验证 SDK retry/timeout/output/并发、thinking guard 和未知费用停止；本专项通过不能替代这些门槛。

## 已审快照 SHA256

```text
backend/config.py E3FE228A397BB339CA2AB6A44F02063FC3C8A29D4422B5D2614509DD5DDA47CB
backend/generator.py 2DED1D96676B1F1913071D88D36A370482FD4472C495450B4E043F6E8345014A
backend/retrieval.py 25B5D116659A1AED95A8BD54767EE3287F2587CFC4CCC1C5AFAF154699BEF6E6
backend/conversation.py C6B498CC67E68B619DC8BE963FFFE4CE248470391D201B8C98EAAA5079333973
backend/query_optimizer.py 82B8179DB2542C1E54CEC4757A3167CFA22B2E82EABF8833A984E70C751DA0D0
backend/routes/query.py 0EF967A8145D7E2345DEAE8CDD7F5A2AEEEF743E1F722AFEB2101A6BB77CCA76
backend/routes/rag_query.py D74E27E9AD4B33B355927D4658060CFDD140DD05AD168F82F3016C1DE5966848
backend/pipeline.py BF06FF37D0357B465AAF2A234D642C2ED4728191980D171E8887464475516101
backend/worker.py 30472444CFE062C02AA2A685615FDBCDBB7F9EBDDA27B76CEDF08C11EC99A586
backend/services/bot_handler.py 89218F3EF463B39AFAAA5967718F1B2956FEE3F1E94ADE72047605097C678D81
backend/tests/test_generation_model_selection.py 69911346EA3D8D25797469643A3342ED2410137D8288EDD40217F069C53AF3DA
backend/tests/test_retrieval_generation_readiness.py F773D810A9634600D8853B907BF0CADF8A9C1AAA06979E978B157194D164C33D
backend/tests/test_source_control_integration.py 336AD75B4D89241DAB6CBF6081769D7C03B1F671011AEEDB826CD5A8F82ED931
```
