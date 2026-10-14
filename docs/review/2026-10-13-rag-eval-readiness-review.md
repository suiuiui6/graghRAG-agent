# rag_eval 独立范围与测试质量审查（2026-10-13）

审查总结：本轮离线软件验证的全生产范围、有效行为断言、双覆盖率原始计数与锁依赖审计证据可信；独立复跑全部 74 项测试通过。发现 1 项既有规范漂移，协调者补充当前实现契约后已定点复核关闭；当前本轮阻断发现 0，Critical 0 / High 0 / 未关闭 Medium 0。

## 输入与职责

- 只读审查 `iteration-2/eval-2-existing-components/rag_eval/`，唯一正式输出为本文；未修改生产代码、测试、锁、Gold、历史研究结果或 memory。
- 已读取根 AGENTS、memory/index.md、2026-10-13 记录、测试规范、本子项目规范与能力边界。目录下未发现附加 AGENTS。using-superpowers 按其 SUBAGENT-STOP 跳过，已读取 requesting-code-review 并采用其独立审查原则；本审查是根协调者派发的独立上下文。
- 基线 HEAD `46b202c3e400741fd569f024412c0745f224a538`；工作树有其他任务的大量未提交修改，均保留。作者报告为 `docs/testing/2026-10-13-rag-eval-readiness.md`，原始证据在 `docs/testing/rag-eval-readiness-20261013/`。

## 独立核实结果

1. 枚举全部第一方 Python 文件，剔除实际测试、虚拟环境与缓存后，12 个生产文件与作者清单、coverage JSON 的文件集合完全相等；包含 `build_ground_truth.py`、全部 CLI 和验证入口，没有漏掉未导入业务文件。配置 `source=["."]` / `branch=true`；omit 仅测试和虚拟环境。excluded_lines=0，未发现 skip/xfail/nocover 等新增规避标记。
2. 全部 12 生产文件与 6 个既有根测试分别同 HEAD 比较，换行归一后的源码完全相同。既有测试断言没有删除或削弱；两个新增文件补充 28 项，加原有 46 项共 74 项。
3. `test_metrics_readiness.py` 直接导入真实指标模块、调用实际函数与 `main()`，写入临时合成输入并读取真实 JSON/Markdown。断言包含明确计数/数值、集合去重和排名、缺 run、空集合、拒答误报、关键词、tool request/result 区分、重复签名、百分位、成本与异常分类。不是只验证“无异常”，也没有复制生产函数冒充目标实现。
4. `test_cli_readiness.py` 的 Gold 构建测试通过 `runpy.run_path` 执行未改写的真实源码，仅将该源码的 `pathlib` import 替换成严格允许两个固定路径的 Path 工厂，未知路径立即断言失败。临时 500 节点/空边用于结构、节点存在性与非法节点失败分支；没有读取原 KG 或写原 Gold，不把合成节点当科学 Gold 质量证明。没有替换 `add()` 或指标算法。
5. CLI 测试验证真实临时文件追加/resume、setup 顺序、成功/异常记录、时延回退、缺凭据 guard 与真实 TestClient 装载。HTTP 使用测试 FastAPI app，dotenv loader 在调用前替代；backend/conversation validation 替代 subprocess 边界，只验证摘要/退出码传播。替代边界被报告明确披露，不属于真实后端/供应商集成验收。
6. 独立 Python 核对作者 before/after：22 输入、12 生产、77 受保护文件原运行前后 hash 相同；复跑前当前文件亦全部匹配。输入 map 的 SHA256 独立计算为 `f520bbee160dd7336cf24c60f19ec0670c89b50e5ddd6a5576ed5cc8c47eed6f`，与报告一致。原始 coverage JSON 独立读取得行 **1722/1742 = 98.85189437428244%**、分支 **415/440 = 94.31818181818181%**，两项分别超过 90%，未使用综合分数代替。
7. 独立读取 uv.lock 的 23 个 registry 包、实际环境 importlib.metadata、pip-audit JSON，名称/版本集合完全相等，实际版本漂移 0，23 项 vulns 全空。审计、锁检查、pytest、coverage 导出、snapshot 的原始 `.exit` 均为 0；审计日志保留 no-deps/哈希建议警告，不含忽略公告。这里只核对作者已执行的审计证据，没有重新访问漏洞数据库。

## 实际命令与退出码

- 根目录：PowerShell here-string 输入独立 Python 校验脚本，经 `iteration-2/eval-2-existing-components/rag_eval/.venv/Scripts/python.exe -B -` 执行；读取 snapshots / coverage JSON / audit JSON / uv.lock，枚举源码，计算 SHA256，并通过 `git show HEAD:<path>` 比较原测试与生产源码。exit **0**，上述核对全部一致。
- cwd `iteration-2/eval-2-existing-components/rag_eval`：`.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=D:/graghRAG-agent/.tmp/rag-eval-independent-review-20261013 --tb=short`。Windows TestClient socketpair 按正规 `require_escalated` 批准执行；exit **0**，**74 passed / 1 warning / 1.58s**。唯一警告为 Starlette 的 httpx TestClient 弃用提示，未屏蔽。此独立复跑未重新测量覆盖率，覆盖率结论来自已核源码 hash 和作者原始 JSON。
- 有一次组合只读搜索使用 PowerShell 不展开的 `test*.py` 路径导致 rg exit **1**，随后以目录加 `-g '*test*.py'` 修正，exit **0**；该搜索错误不是测试失败或通过证据。
- 文档补充后再次独立 hash 校验 exit **0**：22 输入/12 生产依然 drift0；77 保护文件中仅 `RAG-EVAL-SPECIFICATION.md` 有意变更，Gold、历史数据与其他保护文件均不变。新规范 SHA256 为 `2f9683cb79e3548d4a358a9654d6d1ab81d6095f917a703a3c871f605425bca8`。这是测试后文档修正，不回写旧 before/after 或声称保护集合仍为零漂移。

## 问题清单与闭环

### 🟡 Medium — 既有规范描述超出当前代理指标实现，已关闭

位置：`iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md` 原 34–50、78–85、129–130 行（补充后历史章节顺延）；`CAPABILITY-BOUNDARY.md` 9–10 行保留历史表述。

问题：历史输入示例用 `relevant_doc_ids`，A2/A3 描述 LLM judge / embedding 语义一致性，实际使用 `expected_node_ids` 与关键词/集合代理。测试可以证明这些规则正确执行，不能证明语义忠实度或完整多跳推理。若不区分当前契约与旧设计，会误解本轮验收范围。

建议及处理：协调者在规范顶部新增“2026-10-13 当前软件验收口径（覆盖旧设计冲突）”，声明当前节点字段、A2/A3 规则、A4 节点覆盖/路径相关代理以及未建设的语义裁决边界。独立对照 A1–A4 源码复核，描述准确；旧能力文档作为历史内容阅读时须按该顶部有效口径解释。未改历史科学结果。

Before/After 规范示例：

```text
Before: Faithfulness = LLM 判断事实一致性；Consistency = embedding 余弦相似度。
After: 当前 A2 按节点有效性/检索引用/关键词/拒答规则计算；
       A3 按硬编码规则与显式噪声题目映射计算，不调用 LLM judge 或 embedding。
```

Critical/High：未发现本轮新增问题。TypeScript：本范围不适用。未对未变更的全部历史产品逻辑出具无缺陷保证。

## 优先级与结论边界

1. 本子项目离线范围与测试质量审查通过，根协调者可将其纳入分项目证据汇总；规范漂移已回流关闭。
2. 保留真实供应商、完整后端生产链、科学 Gold/语义裁决与研究冻结的独立验收要求；本轮替代边界测试不能替代这些证据。
3. 提交前仍须由协调者核对全项目适用子项目最终快照、双指标、安全与其他规定门槛；当前仅 `audit-only-windows`，本报告不证明可信 CI、分支保护或全项目可提交。不曾 commit/push/deploy。
