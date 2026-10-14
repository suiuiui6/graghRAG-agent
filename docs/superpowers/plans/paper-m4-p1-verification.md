# M4-P1 实施与验证记录

项目：`graphrag-paper-001`；日期：2026-10-07；SCI-Skills；不使用 goal。

## 验收结论

P1 来源控制与有效配置的软件范围通过；M4 仍为部分通过，P2/P3 未实现，不进入 M5。全部更改限定本项目；未修改全局技能、其他项目、前端、索引或历史论文结果，未提交 Git。

已实现请求级 `enabled_sources`，覆盖 normal、global/community、global-local 回退、KG/BM25/Table retrieval rescue、KG/storage-vector generator rescue 及候选图谱补投影。禁用路径在调用前拦截；默认 null 保持兼容；非法列表 422；显式来源请求主链不可用 503，不进入 legacy。请求级配置及执行账本不修改共享 pipeline.config。

`metadata.effective_config` 记录规范来源列表、权限/feature 依赖、预算、路由、分阶段 executed/failed/skipped、候选计数及 CE 实际状态。失败计数 null；真实零命中 executed/0；未触发补证 skipped/query_condition。变体生成失败不是零命中，合法空变体未调用向量源，记 skipped/query_variants_empty。prompt 预算单独记录。完整接口契约已回流 `integration/backend-api-architecture-v1.0.md` 与评测规范。

## 实际执行证据

使用已有 `backend/.venv` 的 Python 3.12.8，无安装或下载。测试先 RED，再实现及复审修复；新增测试最后 29 项单元 + 17 项真实本地集成，另 107 项选定回归，共 **153 passed**。命令从 `backend/` 执行：

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
./.venv/Scripts/python.exe -m pytest tests/test_source_control.py tests/test_source_control_integration.py tests/test_query_budgeting.py tests/test_hybrid_retrieval_trimming.py tests/test_community_global_mode.py tests/test_retrieval_stage_metrics.py tests/test_retrieval_precision_tuning.py tests/test_tail_latency_controls.py tests/test_query_preprocess_guard.py -q -p no:cacheprovider
```

真实集成使用生产 FastAPI router、实际 BM25 索引、真实 SQLite 改写缓存重放、ConversationManager 和 LineageStore 隔离目录；禁止网络边界调用。query/summarize 验证确定性纠错，retrieve 验证真实召回，另验证 null/省略默认、422、503。单元测试用 TEST_ONLY 夹具和边界替身验证调用隔离、并发请求不串配置、各补证条件、内部失败与零命中的区别。替身不冒充真实依赖或科学结果。

两项原有环境警告保留：pytest `timeout` 配置未识别；jieba 的 pkg_resources 弃用警告。不安装插件/升级依赖来掩盖警告。ruff 不在后端 venv 中，未运行或安装。8 个相关 Python 文件静态语法检查、SCI 状态 YAML 解析与 git diff --check 通过；历史哈希与先前一致。Git 提示 LF/CRLF 转换，不是差异格式错误。

只读复审修复了补证未触发记录、storage embedding TypeError 被吞、Table rescue 异常被吞、normal Table/Multi-Query 内部失败误记零命中和 API 契约不完整问题。最后一次静态复审未发现剩余 Important；复审不冒充再次执行测试，153 项测试由主会话实际运行。

## 未执行与保留边界

- 未加载 embedding、Cross-Encoder 或生成模型；未调用远程服务；未执行七变体或整套依赖模型的集成测试。
- 真实依赖集成仅覆盖本地 BM25/缓存/确定性回答链，不宣称 vector/model 完整集成通过。
- raw_candidates_total 仍为 null，不能据此宣称预算匹配完成。稳定证据 ID、实际可见 context、decision_evidence/raw-answer 属于 P2，冻结运行和科学裁决属于 P3。
- 历史 ground_truth、raw_runs、backend/uv.lock 的 SHA256 与先前记录一致。HEAD 加 dirty tree 不等于冻结实验版本。

下一步：M4-P2，稳定证据身份、上下文与答案链追踪。
