# 向量存储隔离 MVP 独立审查

日期：2026-10-13。范围：合成能力探针、锁/实装/已有审计对账；不是完整适配层或产品集成验收。

## 审查总结

阶段1审查完成：独立复跑Lance 12项、SQLite 8组局部断言均通过；Lance过滤18项与作者冻结逐项一致，重新计算对Chroma仍有5项差异。探针路径与退出码合理，未发现读取 .env、真实 output、Gold 或调用模型的代码。结论为**原生能力阶段通过、直接兼容BLOCKED**。记录 High 1 项适配兼容缺口、Medium 1 项运行限制、Low 1 项后续实现建议，Critical 0 项；完整替换、迁移与安全交付尚未验收。

## 证据和独立核对

- 作者目录 `.tmp/vector-replacement-mvp-20261013/` 只读；评审可执行产物放独占 `.tmp/vector-replacement-independent-review-20261013/`。数据库均按各自脚本 `__file__` 目录生成时间戳名称，未与作者共享 DB。
- 独立 `verify_identity.py` 用候选 `.venv/Scripts/python.exe` 执行 exit 0：17 registry锁项 = 17实际安装 = 17审计项 = runtime-registry清单，版本与集合完全相同，保存审计所有 `vulns=[]` 且 `.exit=0`。这是已保存扫描证据的独立核对，没有重新联网扫描。历史44包工具混装锁和失败安装记录未被当成最终运行集合。
- 主要版本：Python 3.12.8 / NumPy 2.5.4 / PyArrow 26.0.0 / LanceDB 0.40.0。SQLite 运行库 3.45.3，不在 PyPI 17包审计覆盖内；不能据零 PyPI 公告声称原生运行库已审计。
- 作者 `probe-01` 沙箱启动受阻后中断，exit 1，无探针结果；`probe-02-approved` exit 0，12个局部check PASS。错误历史被保留，未以成功覆盖失败。
- 作者 SQLite 原脚本复制到独占目录后实际独立重跑 exit 0，8组行为断言通过：绑定参数、metadata/float32 BLOB、重复主键、事务回滚、backup/清空恢复、子进程重开、5000×512自查询top1。未修改其脚本内容。

输入hash及命令/结果见独占 `identity-review.json`、`sqlite-independent.log`、`sqlite-independent.exit`。初始源脚本 `probe.py` SHA256 `9d9983bb0085cda1a4d92f535d8e74faac55b84c987df15179d0a333de355e79`；`sqlite_reference.py` `106f244e652b2497fd9eb55dedd9bc629dc61561990ff0d4d4f5223bf0011ea3`；运行锁 `ab27e2d7dc601aeff7b004502382ef329128115f7812b76f26e72699fe99986d`。

## 问题及限制

### 🟠 High R3：当前过滤映射不具备 Chroma 语义兼容性

位置：`filter_differential.py` 的 Lance `mapped`；`filter-differential-summary.json`。

真实合成差分18项，13相同、5不同：Chroma1.5.9的 `$ne/$nin` 包含缺失字段记录，Lance原SQL比较过滤掉NULL；`active=1`、`page=True` 在Chroma返回空集合，探针严格字段类型拒绝；完全缺失字段的 `$ne` 在Chroma匹配全部，探针白名单拒绝。作者记录 `NATIVE_CAPABILITY_PASS_COMPATIBILITY_BLOCKED` 正确；不能因为合法标量和注入案例通过而宣称完整where兼容。

这是当前最小映射尚未实现适配语义的证据，不是Lance数据库不可适配的证明，也不是要求本轮扩写生产adapter。后续必须依照差分定义缺失/类型/presence语义（例如负向比较对缺失项的处理），未知metadata键不能凭SQL拼接解决。选择有意收紧契约时需显式决定，不能以安全名义默改返回值。

```text
before: col('source') != lit('s1') → 缺失source记录消失。
after: presence-aware过滤AST按锁Chroma差分处理缺失项；
       同时保持字段名/字面量安全构造与有界输入。
```

退出标准：后续适配兼容验收需这5项及完整契约矩阵一致或有明确批准的行为变化。freeze脚本断言“正好5差异”只固定当前发现收据，不是允许5差异的产品通过门槛。

### 🟡 Medium R1：Windows 并发写入出现版本提示文件拒绝访问

位置：`probe-02-approved.log` 的 `concurrent_append` 阶段；`probe.py` 的并发探针。

现象：12独立连接/4线程追加得到15条唯一记录，断言通过；同时 Lance 原生日志报告 `latest_version_hint.json` 写入失败、os error 5。当前证据只证明该次可读取完整集合，不能据此承诺长期多进程提交、崩溃恢复或无Windows文件锁问题。

建议：报告保留原始warning；未来候选选型/集成前核对提交版本/重新打开/长期并发，以及设计中应用写锁能否控制该路径。不能直接把warning当数据损坏，也不能隐去它。

```text
before: 并发追加PASS，因此Windows并发可靠。
after: 本次4线程追加集合断言PASS；出现版本hint写入os5警告。
       多进程/崩溃/长期稳定性NOT_RUN，后续需真实验证。
```

### 🟢 Low R2：过滤探针不是可直接用于生产的完整 AST 防护层

位置：`probe.py` 的 `predicate`。

问题：当前仅固定字段类型、每层逻辑列表/集合长度及递归深度，没有全局节点预算。固定合成调用不构成外部输入入口；但若将该函数直接复用为产品过滤器，32叉嵌套仍可能造成巨大总节点量，也尚无完整Chroma缺失字段/类型差分。

建议：保留探针用途标识；未来适配器按设计加入全局节点计数并完成契约差分，不扩大当前工作为生产实现。

```text
before: depth <= 8、每列表 <= 32，即完整资源上限。
after: depth/局部长度是当前探针限制；生产AST另加共享总节点预算，
       达预算显式invalid_filter，不回退无过滤查询。
```

## 宣称能力的边界

- Lance 原生 `add` **允许重复ID**，当前PASS是正确揭示非能力，绝非兼容 `VectorStore.add_chunks` 已实现；不能在适配器中未经Chroma差分就改成upsert。
- Lance 两种坏批次维度/整数转换错误后计数不变，支持这些输入路径的无部分写入；不证明执行中强制终止、磁盘满、所有失败路径事务原子性。
- 错维度查询被拒绝，但原生错误文案为找不到向量列；产品需明确维度错误分类，不能将当前native异常当稳定API。
- 二进制float64原载荷回读一致，同时派生float32损失约 `7.25e-9`；正确暴露精度边界，尚未证明其跨进程/导出/快照恢复保真。
- 随机规模测试只断言查询自身top1；三条正交向量支持1/0.5/0分数映射，不足以证明完整随机top-k、并列排序和过滤后足量返回等价。
- SQLite warm计时排除了数据库读取、stack/归一化；Lance计时包含每次存储search。两组p95不能直接相减或据此选型。当前30次无独立预热与RSS，保留为初步记录，不对未确认产品预算判通过。
- 5000条规模、单表扫描不证明设计5001分页固定G。完整适配器、全metadata where语义、全量导出/一致快照、2写4读进程、崩溃/磁盘故障、应用级屏障、真实消费者、原生库审计及产品规模均NOT_RUN；其中18个where差分已执行并发现上述5项差异，不能将整个过滤检查记作NOT_RUN或PASS。

## 优先级与结论

1. 先冻结作者结果/脚本/锁并独立核对，局部通过和NOT_RUN逐项分列。
2. 保留R1警告与性能口径差别；阶段报告可以记录候选可运行，不能决定已全面兼容或可安全移除Chroma。
3. 选型与集成前按设计及实际规模补必要证据；没有必要为当前阶段报告形式完整而扩测产品或重复全后端覆盖测试。

## 阶段1冻结及独立复跑闭环

作者正式报告SHA256 `5a33ee4f108e54a22abf7ce2c0d364a0c1147637b184017deb52c2200fb334c5`；永久40文件manifest SHA256 `2d823ba78b78574e7a95680257a498c80501f150cffb8c0841be34ae3f131d23`。独立 `finalize_review.py` 逐一核40文件尺寸/hash，3份复制源与冻结脚本字节相同；重算17锁/安装/扫描集合仍一致。命令均用作者锁定候选Python、cwd为评审独占目录：

| 命令 | 退出码 | 结论 |
|---|---:|---|
| `python verify_identity.py`（复跑前及后） | 0 | 17实装/锁/已有审计集合一致 |
| `python sqlite_reference.py` | 0 | 8组局部断言通过；log/exit保留 |
| `python probe.py`（正规沙箱外审批） | 0 | 12项PASS；独立重现Windows版本hint os5警告 |
| `python filter_differential.py lance`（正规沙箱外审批） | 0 | 18状态/ID与冻结Lance逐项一致 |
| `python finalize_review.py` | 0 | 40冻结文件完整；对冻结Chroma重算同5项差异 |

最小真实探针仅写评审独占合成DB，未复跑Chroma客户端或后端全量。证据位于 `.tmp/vector-replacement-independent-review-20261013/`：`lance-independent.log/.exit`、`filters-independent.log/.exit`、`sqlite-independent.log/.exit`、三份实际结果JSON、`identity-review.json`、`final-review-receipt.json`。最新脚本/锁hash不变；仅作者正式报告与冻结收据支撑结论，不以作者自报代替独立执行。

设计回流已定点核对SHA256 `fc0f393613cc20c6cfae41aea31e247fd7ca7808dcd316963b8797d5a7f7ae3d`：presence/显式类型、未知合法键、key作为literal、未证实组合先差分、完整同G候选语义过滤后再top-k，方向正确；不再把当前固定字段mapper当兼容实现。完整适配差异仍阻断，r2后续结果必须另行独立复核，本阶段冻结及失败历史保留。

本阶段审查已完成；无产品/主锁/原数据修改，无提交/推送/部署。仅独立报告与隔离复验产物新增，不解除现有Chroma公告或项目交付阻塞。

## 原生组件审计范围补充

2026-10-13独立查询 [SQLite官方CVE说明](https://sqlite.org/cves.html)：本轮SQLite3.45.3低于官方所列CVE-2025-3277/29087修复版3.49.1、CVE-2025-6965修复版3.50.2、CVE-2025-7709修复版3.50.3及CVE-2026-11822/11824修复版3.53.2。官方说明相关问题有攻击者可执行任意SQL、控制数据库内容或FTS5/defensive配置等前提；**版本比较不是可利用性结论**，当前未执行漏洞利用或完成部署路径适用性审计。

已有零公告仅指Python运行依赖17项的pip-audit结果；Python自带SQLite DLL、Lance Rust及Arrow等嵌入二进制未完成SBOM/底层依赖审计。合成探针不接收外来SQL/DB，但不能代替未来导入/恢复入口的威胁模型与原生运行库验证。本轮不替换Python/DLL、不自动淘汰SQLite，也不把减少PyPI包数量视为安全清零。原生安全证据不足作为后续选型/集成交付限制保留。
