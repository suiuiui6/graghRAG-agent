# R6 隔离替换候选独立评审

## 审查总结

2026-10-14 局部设计审查：有条件通过，可以按下列约束实现隔离候选；实现及实际攻击输入验证尚未执行，不是生产集成准入。设计未发现不可实施的根本阻断，列出 4 项 High 实现验收条件、2 项 Medium 证据条件；尚无关闭的代码问题。

输入为 [R6 合同](../contracts/2026-10-14-vector-r6-semantics.md)、[计划](../plans/2026-10-14-vector-r6-isolated-fix.md)、[R5 异常合同](../contracts/2026-10-14-vector-error-semantics.md)、R5 作者及独立报告，以及当前 `backend/logging_config.py`。应用 requesting-code-review 的独立检查协议。本 reviewer 只负责本报告与独占 `.tmp/vector-r6-review-20261014/`；不修改生产、其他任务文件或旧冻结，不提交。

## 问题清单与接受条件

### 🟠 High：动态栈帧和类别名称仍可泄露任意值

- 设计位置：R6 合同第 7–9 行；当前生产 `backend/logging_config.py` 的 setup_logging/format_exc_info 路径（本轮不修改）。
- filename 的 basename、function 的 `co_name`、exception 的 `__name__` 均可由动态编译或类型创建控制；仅去路径、限制字符集或限制长度不构成任意裸标记保护。
- 建议：以审核过的已加载函数 code object 身份映射固定 `(file,function)` 标签；异常以 exact class identity 映射静态类别；未知来源输出固定 `unknown_frame`/`Exception`，保留数量及行号。不以动态字符串等值判断“已审核”。固定代码标签与行号须能回溯到冻结源。
- Before：`{"file": Path(code.co_filename).name, "function": code.co_name, "type": type(exc).__name__}`。
- After：`{"file": audited_code_labels.get(code, UNKNOWN)[0], "function": audited_code_labels.get(code, UNKNOWN)[1], "type": audited_type_labels.get(type(exc), "Exception")}`。此为设计示意，身份表不得依靠可伪造字符串注册。

### 🟠 High：只删除 exc_info 或 error 不足以保护 typed 事件

- 设计位置：R6 合同第 7–11 行。
- event、logger、contextvars、额外 exception/error 字符串及嵌套容器都可能含同一原始标记；现有通用 redact_sensitive 是模式扫描，不能提供本轮任意值保证。
- 建议：typed 向量错误日志整体重建安全白名单；固定 event ID、固定枚举 code/operation、确切类型验证的安全遥测及结构化诊断。未审核键和值均不得传递给后续 renderer。是否存在 typed cause 但顶层是普通 wrapper 必须明确，建议预算内发现 typed 错误即应用安全路径。
- Before：`event_dict.pop("exc_info", None); event_dict["exception"] = safe_trace`。
- After：`event_dict = {"event": FIXED_EVENT, "vector_error": safe_diagnostic, **validated_telemetry}`，不将任意原 event_dict 合并回结果。普通非向量事件继续旧策略，其任意值安全不在承诺内。

### 🟠 High：异常遍历不得执行用户代码或重新格式化异常

- 设计位置：R6 合同第 7–9 行。
- 恶意 `__str__`/`__repr__`、异常子类 `__getattribute__` 或动态类型名可能在日志过程中再次失败或产生泄漏。
- 建议：禁止异常 str/repr、args/locals/source-line；cause/context/traceback 采用 BaseException 原生 descriptor 读取，类型输出按静态身份表。code/operation 也须确切类型和固定枚举，不直接信任异常可变属性。无法安全识别的值用固定未知标识；不得因此删除内部 cause。
- Before：`str(exc); exc.__cause__; type(exc).__name__`。
- After：`BaseException.__cause__.__get__(exc); STATIC_CLASS_LABELS.get(type(exc), "Exception")`，仅遍历安全的内建 traceback 结构。

### 🟠 High：循环/长链预算与诊断保留需同时成立

- 设计位置：R6 合同第 9 行、计划第 4–5 步。
- 无循环检测会无限遍历；单纯输出固定错误或抹除 cause 会丢掉实际失败定位。
- 建议：按对象身份循环检测，显式链数/帧数预算与截断标识；保留 cause/context 关系及静态帧定位。原始 exception、cause/context/traceback 身份保持不变。测试断言单次 search、failed/count=None、链类别与有效帧存在，以及 console/file 均无标记。
- Before：`while exc: exc = exc.__cause__`。
- After：有界队列/遍历配合 `seen_ids`，输出固定 `cycle`、`truncated` 状态，内部对象不变。

### 🟡 Medium：宽 record 机制尚需原生证据

- 合同第 5 行：不将旧 3 个观察值泛化为所有宽整数，也不因候选拒绝而宣布分类一致。
- 接受条件：debugger 核 PyO3/原生实际转换，正负 I64/U64 边界、巨大整数、float bits、持久化重解析及 where 消费独立验证。不得查表、丢字段、浮点容差弱化。NaN query 策略仍单列 GAP；未测机制不放行该项。

### 🟡 Medium：当前消费者证据须重新绑定

- 当前 `backend/retrieval.py` 等存在其他任务改动，旧 source 全文件 SHA 和旧双90不可作为当前全树证据。
- 接受条件：冻结当前实际执行的 3 个 AST 函数内容及原文件 SHA，采用真实 logging 配置链的隔离副本，只插入候选 processor；声明函数 subset、故障注入和真实依赖各自范围。最终代码冻结后独立新输入复验，作者红/绿命令及退出码独立保存。

## 优化建议汇总

1. P0：按上述 4 项 High 条件实现安全 typed 日志路径并独立验证，完成前不能标日志任意值缺口关闭。
2. P0：核原生宽 record 机制再修复，区分投影值、原 payload、兼容 readback。
3. P0：最终冻结后执行独立攻击输入及数值新输入，核现有受影响回归，不据作者自报直接关闭。
4. 保持 NaN 正式策略、formatter 全域、原生安全、完整生命周期/API/worker/迁移开放；本轮隔离修复不会消除现役 Chroma 四公告。

本阶段实际执行仅为只读文档/源码/工作区检查，未执行候选测试、产品全量双90或安全扫描。任务负责人统一更新 memory；下一轮收到最终候选快照后追加实现审查与实际命令结果。

## 2026-10-15 接续实现预审（尚未冻结）

审查总结：当前日志候选尚不能通过，实现预审发现 1 项 High 阻断和 1 项 Medium 行为说明缺口。宽整数旧断言的修订有原生证据支持；最终快照与完整适用回归尚未收到，不关闭原设计验收项。

- 🟠 High，`.tmp/vector-r6-20261014/safe_vector_logging.py` 第 6、21、39 行：`_TYPED` exact identity 识别会遗漏所有未知 `VectorStoreError` 子类。短链的该类事件直接走 `return event`，原 `exc_info`、任意 event/extras 和裸 cause 会交给真实 formatter。独立 `precheck.py`（本 reviewer 独占 `.tmp/vector-r6-review-20261015/`）实际 exit 1，`typed_subclass_sanitized=false`，恶意元类/实例属性钩子调用 0 次、cause 身份未变。建议将“识别 typed 继承边界”和“静态类别输出”分开：识别通过真实 `type(obj)` 与内建 type 的原生 MRO descriptor 做身份检查，输出继续 exact class label，未知子类固定 `Exception`。Before：`any(type(current) is t for t in _TYPED)`；After 示例：`any(base is VectorStoreError for base in type.__dict__['__mro__'].__get__(type(current)))`。异常提取入口也避免对任意未知值使用可能访问 `__class__` 的 fallback 检查。必须补真实 console/file 及消费者 subset 的子类红绿验证。
- 🟡 Medium，同文件第 36–47 行：诊断预算后的额外发现遍历即便排空且不存在 typed，原 `queue` 仍非空，普通 40 层异常链也会被重建为固定 `vector_store_failure`。独立预检实测 `ordinary_long_chain_rewritten=true`。这是可接受的 fail-closed 取舍，但合同必须明确：预算内确认普通事件可沿用旧策略；未能在主诊断预算内确认时会牺牲普通长链的原消息/类别和任意 extras。不要声称所有普通日志均保持原样。

宽整数断言复核：debugger 已核 Chroma 1.5.9 的 bool→i64→f64 提取机制并实测 `2**63` 接受。因此仅修改新 R6 的旧 `2**63` 必拒绝断言，换为接受、raw metadata 精确 int、compat 与投影 float bit 一致；以 `10**400` 保留真溢出拒绝，符合合同且不是降低输入质量门槛。旧冻结和原 exit1 证据必须保留。

优先级：先修子类识别 High，并明确预算 fail-closed 普通事件行为；再冻结代码，独立运行恶意属性/元类、伪造 code、动态类别、任意 extra、循环长链、真实 console/file、当前消费者 AST subset，以及新的宽整数位级/过滤差分。当前不是完整 worker/API 验收，也没有产品全量双90、提交、推送或部署结论。

## 2026-10-15 最终冻结独立实现复审

审查总结：在本轮所测隔离范围内条件通过，当前没有未关闭的阻断问题。本轮实现审发现的 1 项 High（typed 子类漏识别）及 2 项 Medium（普通长链降级说明、共享节点误称 cycle）均已通过代码/合同修订与独立实测关闭；原设计列出的安全条件在以下有界验证中满足。完整替换与生产准入仍不通过本报告。

### 冻结与独立执行

权威清单 `docs/testing/vector-r6-20261014/r6-freeze-manifest.json` SHA256 为 `37a4ca29ce343e1621235b1bb8fdbee52beb120b67134fc3b32d1e6c1d1fbac5`。本 reviewer 亲核 **186 个归档文件、38 个最终执行输入**，全部 hash 一致；逐项复制到独占 `.tmp/vector-r6-review-20261015/frozen/` 并复核。独立执行结束再核归档/私有复制/执行输入，漂移均为 **0**。执行收据及每项证据 hash 见 `.tmp/vector-r6-review-20261015/execution-receipt.json`，不是作者自报。

实际命令（以下路径相对仓库根；native 两端及日志消费者均经正规 `require_escalated`）：

| 命令 | 退出码 | 范围 |
|---|---:|---|
| `.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/vector-r6-review-20261015/verify_freeze.py` | 0 | 全清单/执行输入/私有复制核 hash |
| 同一 Python，`precheck.py .tmp/vector-r6-review-20261015/frozen` | 0 | 独立先前有效红的 typed 子类回归；恶意元类/实例钩子 0 次，cause 身份保留 |
| `.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-r6-review-20261015/independent_numeric.py .tmp/vector-r6-20261014 chroma` | 0 | 新 seed `84015619` 的真实 Chroma oracle；32 记录、90 where、get/query |
| 独立测试环境 Python，`independent_numeric.py .tmp/vector-r6-review-20261015/frozen lance` | 0 | 同一新夹具真实 Lance；raw/type/bits/投影及 get/query 差异 0，真正溢出拒绝保留 cause |
| 独立测试环境 Python，`independent_logging.py .tmp/vector-r6-review-20261015/frozen` | 0 | 最终夹具 6 个真实 console/file 安全事件、恶意钩子 0 次、3 个实际消费者函数 subset |
| 独立测试环境 Python，`final_receipt.py` | 0 | 执行后归档/私有复制/38 输入漂移 0 |

`independent_numeric.py` 的 Chroma 分支只生成 oracle，不加载候选，因此先于私有复制生成 oracle 不影响冻结绑定；Lance 分支仅从已核私有冻结加载实现。先前日志预跑在作者同时将字段更名 `cycle_or_shared` 时触发旧测试字段 `KeyError`，不是安全处理失败；最终测试已跟随正式诊断字段并亲跑 exit 0。初始预检构造恶意异常时自身触发属性断言也已修正为原生初始化，独立真实漏洞红 `precheck.json` 保持 `typed_subclass_sanitized=false`；最终 `precheck-final.json` 为 true，未抹掉红证据。

### 问题关闭与行为证据

- 🟠 High 已关闭，冻结 `safe_vector_logging.py` 第 8–9、18–25、42 行：`_inherits` 通过 `type(value)` 与内建 MRO descriptor 做身份检测，typed 继承边界和 exact 输出类别分离。未知 typed 子类输出固定 `Exception`，不输出其动态类名；恶意元类/实例 `__getattribute__`、`__str__`、`__repr__` 及伪造 `__class__` accessor 均未调用。原 cause/context 对象保留。Before 为 exact `_TYPED` 检测直接漏放子类；After 为原生 MRO 身份检测并重建整条事件。
- 🟡 Medium 已关闭：普通长链无法在诊断预算内确认时固定重建 `unknown/truncated` 的保守策略已回流 R6 合同，独立 600 层隐藏 typed 和 40 层 ordinary 链均有界完成。普通短事件保留旧策略；不保证普通日志任意值脱敏。
- 🟡 Medium 已关闭，冻结同文件第 49 行：共享引用与环统一标记 `cycle_or_shared`，合同及作者测试明确首遇关系摘要，避免把 `cause=context` 指同一对象误报成精确环。Before：`cycle`；After：`cycle_or_shared`。链条没有 parent index，因此不是完整异常图；当前固定类别、关系摘要、位置和预算标记满足本轮有界诊断需求。
- 帧映射及事件重建复验：已注册实际函数 code identity 输出固定标签；`code.replace` 产生的伪造 filename/function 不被注册，固定 `unknown_frame`。动态异常类名称、logger/contextvars/event/error/exception、嵌套 extras 中的裸标记与恶意对象全部不进入两路输出；被篡改的 code/operation 变为固定 `unknown`。注册 code 引用与实际 traceback 保留。只校验 scalar 遥测的白名单，不拷回未审核字段。
- 宽 record：独立 32 记录含正负 I64 边界、超 I64/U64、多数量级随机宽 int、最大有限 binary64 对应的正负 int、signed zero。90 条比较/集合顺序/溢出过滤中，真实 Chroma/Lance 的 get 与 query 各自一致；兼容读回类型和 float bits、raw JSON 原类型和值、投影标签和值均独立断言，差异 0。`10**400/-10**401` 保持 `invalid_input` 且保留 overflow cause。该新夹具不同于作者 seed `2026101559`，不能外推为任意 formatter 等价证明。
- 消费者：亲核 4 份执行 copy 与当前 backend 源的全文件 SHA 相同、3 个 retrieval AST 函数含行号一致，收据 `consumer-source-check.json`。独立执行实际 `_search_vector_store_with_projection`、`_vector_recall`、`multi_path_recall` 和真实日志配置链，实际 Lance 成功/零命中分别 `executed/count=1` 与 `executed/count=0`；注入 backend ValueError 为 `failed/count=None`，三种情况各查询一次，失败不重试。故障是明确标记的注入，不冒充真实完整 I/O 故障或完整 worker/API。

### 优化建议汇总与出口

1. 本轮日志子类泄漏和宽 record 已测缺口可以在隔离 MVP 范围内关闭；root 仍须独立复验并统一最终合同/记忆，不以本报告代替其执行。
2. 保持 formatter 任意 binary64 依据、完整 adapter CRUD/分页/快照/并发恢复、完整 worker/API、生产集成与迁移各自开放；本报告没有运行产品全量双90或供应链审计，也不清零现役 Chroma 公告。
3. NaN/±Inf query 的正式拒绝策略已由用户确认，不再列为未决产品 GAP；作者最终冻结专项验证 list/tuple 全位置拒绝且底层查询不执行，本 reviewer 的独立新数值输入仅验证有限输入及真正溢出，不冒称另行复跑该 18 组合。

本 reviewer 仅修改独占审查目录和本报告；未改生产、主锁、旧冻结、coder 目录、数据，未提交/推送/部署。日期记忆由 root 按项目约定统一更新。

## 最终规范回流有界复核

2026-10-15：只读复核 R6 合同最终节、总体替换设计顶部、计划执行出口及原生审计最终节，未发现新增阻断。SBOM 的 20 条记录/18 个唯一漏洞 ID 与不完整 PE 静态恢复的 9 条记录已分清，未把版本匹配宣称为函数可达或已证可利用；61 文件归档作为安全证据入口。R6 仅为所测隔离正确性通过，Lance 安全门槛仍 BLOCKED；SQLite+NumPy 仅优先进入精确安全 runtime 验证，未被宣称安全或已实现。生产不集成、不迁移，现役源码漂移后旧双90不代表当前全树，限制一致。

非阻断措辞建议已交 root：将设计中同日早期“尚待复审”段显式标历史；合同 PE “另有9条”写成“该PE不完整恢复匹配9条”，避免误读为与20条相加。此次没有重跑已冻结代码，没有扩大为完整架构审查或原生漏洞可利用性证明。
