# 本地 v2 工具软件验证记录

日期：2026-10-08。仅新增本地研究工具，不接生产查询链，不执行真实 B0/受控模型实验。作者选择在当前 master 目录实施；未提交或推送。

## 交付与验证

四模块：`backend/research/gold_v2.py`、`scope_v2.py`、`source_mapping_v2.py`、`local_scope_v2.py`。说明：`backend/research/LOCAL_SCOPE_V2.md`。B0 元数据快照：同目录 `b0-readiness-20261008.json`。

实际命令：

```powershell
backend/.venv/Scripts/python.exe -B -m pytest --noconftest -p no:cacheprovider backend/tests/test_gold_v2.py backend/tests/test_scope_v2.py backend/tests/test_source_mapping_v2.py backend/tests/test_local_scope_v2.py backend/research/test_deepseek_scope_pilot.py -q
```

**102 passed，1 warning，6.03s，exit 0**：新工具74项、旧adapter回归28项。警告为现有 `timeout` pytest 配置不被当前环境识别；未安装pytest-timeout。单独 `check` 返回 `LOCAL_SOURCE_BINDING_PASS`：9题、31条目、125必需/25可选属性、172精确证据关联、3源文档。

TDD 先观察缺失实现失败；复审缺口也先加失败测试后修复：空集合 evidence 缺 exact_text、FIG 附录名抢占清单路由、ATTENTION 章节号尾随句号、重复标题泄漏、正文年份被当标题、代码示例被当子项、未闭合代码块尾部被当完整边界。独立最终规范审查 PASS、随后独立代码质量复审 PASS；后者独立运行46项scope测试通过。

## 真实来源的软件夹具检查

下表来源选择均为 **EXPLICIT_TEST_FIXTURE_ONLY_NOT_PRODUCTION_SELECTION**。测试可读取Gold问法/目标做断言，但AUTO实现仅接query与独立传入的源文结构；不接题号、答案或Gold范围。不是留出研究实验。

| 问题 | AUTO 输出 | UTF-8字节（含分隔符） | 目标可见覆盖 |
|---|---|---:|---|
| D1-FIG-v2 | 全文结构扫描，12个正文/附录题注跨度 | 1263 | 原文整篇PARTIAL；投影自身COMPLETE_SCOPE |
| D1-COST-v2 | 摘要 [55,1097) | 2581 | COMPLETE |
| D1-LIMITS-v2 | 6.2 [19694,20159) | 1295 | COMPLETE |
| D1-FUTURE-v2 | 第4项 [20059,20157) | 278 | COMPLETE；无需其他不足项 |
| D2-ATTENTION-v2 | 3.2.3 [12251,13474) | 1233 | COMPLETE |
| D2-DATA-v2 | 5.1 [20861,21487) | 626 | COMPLETE |
| D2-NONE-v2 | 完整3.2.3 [12251,13474) | 1233 | COMPLETE；不是自动否定评分 |
| D3-TOOLS-v2 | 3.2 [6399,6809) | 564 | COMPLETE |
| D3-SUPERVISOR-v2 | 4.1 [11015,11170) | 283 | COMPLETE |

所有映射逐字吻合LF Unicode codepoint原文切片。字节预算不是provider token预算。FIG带源hash/检测器版本的本地扫描证明不等于整文档模型输入，也不保证任意布局下题注识别穷尽。NONE空检索不能当否定证据。报告默认不公开原文/组装文本，歧义候选仅输出来源坐标。

## 完整性与语料发现

实际 `prepare-b0`：冻结v2和源/上游hash通过；生产15文件、原文3份、旧实验62文件均与冻结checkpoint一致。未将旧27回答按v2重评分。

只读Chroma `rag_docs`：512维、1440条；至少20字符的整段逐字匹配方法找到D1共31段、均唯一，但仅1段stored span有效，30段坐标未直接对上。候选定位不自动修复，不套全局+1。D2/D3本方法0匹配不是缺失证明或模型失败。DB前后SHA-256一致，WAL/SHM均未出现。

BM25/table/docs-store持久化数量为3/2/83。数量/hash/文本匹配不能替代生产进程实际加载的语料身份或检索过滤；runtime与源选择仍UNKNOWN/SOURCE_UNRESOLVED。

## 安全边界与未覆盖项

四模块AST/import检查通过；仅标准库、本地模块与现有PyYAML，无生产模型/检索/config导入、环境/key读取、供应商调用、模型加载、服务启动、入库或重建索引。CLI子进程仅只读git身份/差异指纹；原始diff在内存hash，不输出。

ruff、bandit、pip-audit、detect-secrets在现环境不可用，未安装/联网，不宣称这些扫描完成。语法检查/人工静态审查不等于漏洞扫描。只验证选定新工具和旧adapter，不宣称整个生产仓库全量测试通过。

原PDF视觉核验、人工Gold认证、真实检索/生成、运行模型、调用上界、provider usage、隐私导出和远程权限均未被这次软件检查完成。限定结构规则不是通用Markdown/PDF语义解析。

## B0准备状态与唯一下一步

快照状态 **BLOCKED_NOT_EXECUTED**，不是可执行请求包/API授权。B0_NATIVE与三受控路径分开；原生检索、rescue、prompt、后处理、extra_body封装及重试须保留。受控复用同版本新捕获上下文/预处理；trace的fallback变化须登记，document_id回显不视为过滤。

54次仅为条件性有限批次提案；无新调用授权，不推定人民币预算上限。合法传输/脱敏映射、运行/语料身份、真实源选择、cache/session、完整调用图和请求设置均未冻结，不能执行新波次。M2仍开放，不据此宣称方法收益、普遍性、新颖性或期刊层次。

唯一下一步：核验真实B0运行身份、语料身份及上下文来源映射，保持原版生产路径不变，再单独登记新有限执行范围。
