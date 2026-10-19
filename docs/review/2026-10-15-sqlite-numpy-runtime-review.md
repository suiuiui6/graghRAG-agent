# SQLite＋NumPy R7 独立评审

日期：2026-10-15。范围：`docs/plans/2026-10-15-sqlite-numpy-runtime-validation.md`及`docs/design/2026-10-13-vector-replacement-design.md`的SQLite替换范围。读取根AGENTS、memory索引及15日R6最终记录；当前master有其他任务修改，评审者仅写本文及`.tmp/sqlite-numpy-r7-review-20261015/`，未改生产/锁/旧冻结/数据，未提交。

## 设计审查总结

设计条件通过，可在实际runtime版本/能力达标后进入隔离原型。0 Critical、0 High；3项必须落实的验收细化（Medium），尚非已完成实现发现。R7只证明运行库及最小真实I/O，不解除完整Chroma where、原数值契约、adapter、分页及生产门槛。

采用实际安装`requesting-code-review`的独立检查方式。启动技能`using-superpowers`已读，其SUBAGENT-STOP明确要求被分派专门任务的subagent跳过，不重复编排。

## 验收细化

### 🟡 Medium — 可信快照身份不可自证

位置：计划步骤5。备份旁可任意修改的manifest不能成为可信hash来源；必须由已受控备份创建过程返回可信identity，并先校验bytes摘要/尺寸，再让SQLite解析。恢复到全新路径，不覆盖既有目标；失败不能改变原库或留下可被误激活的目标。

建议顺序（契约示例，非实际代码）：

```python
# before: expected = json.load(snapshot_sidecar)
# after: expected = caller_held_trusted_identity
verify_bytes(snapshot, expected)
restore_to_new_target(snapshot, target)
```

hash证明和创建时同一bytes，不证明外来DB安全；不加载外来DB/SQL/NPY/pickle。

### 🟡 Medium — finite入口不能代替派生数值校验

位置：计划步骤4、总体设计的有界NumPy cosine。极大有限元素可能使直接norm溢出；零向量余弦无定义。固定dtype/维度/最大记录与k范围；明确零向量拒绝或其他既定策略，并通过缩放等稳定算法处理支持域内大有限向量。返回score必须有限并位于约定范围；明确并列排序。

```python
# before: normalized = v / np.linalg.norm(v)
# after: validate_shape_dtype_finiteness(v); stable_normalize(v)
```

本原型可以明确有限支持域，但不得以其结果冒称全生产数值等价；禁止悄悄产生NaN排序。

### 🟡 Medium — 每个连接均需硬化并失败关闭

位置：计划步骤3、5、6。进程子连接、读连接、backup/restore连接都在访问schema/数据前实际配置并核验defensive、trusted_schema、extension禁用、资源限额，不仅在发现阶段对一次连接probe。配置失败立即拒绝使用。

```python
# before: con = sqlite3.connect(path)
# after: con = hardened_connect(path)  # configure + assert actual state
```

trusted_schema OFF并非任意SQL执行沙箱；SQL仅固定模板及绑定值，不对外提供原生连接或动态schema。WAL仅本机文件、每进程独立连接；实际并发/冲突/中止范围如实报告。

## 优先级与后续

1. debugger给出固定官方Python3.12 artifact/hash及实际SQLite>=3.53.2/能力；不足保持阻断，不原地替换DLL。
2. coder将上述三项细化纳入先红后绿的真实I/O测试，并冻结最终输入、源码、锁、wheel及运行库身份。
3. reviewer私有复制独立新夹具验证；原生CPython/SQLite/NumPy/OpenBLAS公告由root分项核对。pip-audit0只对应包公告扫描，不能代替原生安全结论。
4. 按最终事实给隔离候选/部分通过/阻断结论。当前尚未执行runtime测试、未进行最终代码审，不能宣称安全准入通过。

## 局部runtime变更设计审（官方SQLite DLL派生组合）

root报告官方Astral CPython3.12.15原artifact实际SQLite3.53.1，低于本轮3.53.2最低要求，不能直接准入。新增实验可在既有隔离授权内执行：将已验artifact复制到全新derived profile，仅替换该副本的sqlite3.dll为SQLite官网下载的精确x64 3.54.0产物；原base、旧venv和系统DLL不动。此处仅为设计接受条件，报告的版本/摘要尚待reviewer亲核最终收据。

0 Critical/High设计阻断；以下条件不得弱化：

- 明确为“官方CPython＋官方SQLite DLL的项目派生组合”，不冒称该完整组合受CPython/Astral官方构建支持或已完成其完整测试。
- 官方精确archive URL、官方发布页SHA3-256须核验并冻结；解压仅提取预期sqlite3.dll，核PE x64和导出/导入依赖。
- 复制base前后完整manifest证明唯一变更是预定DLL；base摘要无变化。记录实际_sqlite3加载路径/依赖及runtime source_id、compile_options、连接配置能力。
- ABI导入成功只是首关；标准库sqlite3最终组合需执行CRUD、批写事务、真实备份/恢复、独立进程并发/锁超时/中止重开，并落实每连接硬化。
- 原生身份/适用公告和pip包审计继续分别给结论；组合测试不能自动证明全部系统DLL或未扫描组件安全。
- 不降低SQLite最低要求，不用APSW安装来掩盖未修标准库DLL。ABI失败时仅保留失败收据，再独立审替代绑定方案。

该局部实验不需要生产切换授权；通过后也只可称有证据的隔离派生候选，不解除完整adapter和生产发布门槛。

## 独立PE静态兼容检查

实际命令：`.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/sqlite-numpy-r7-review-20261015/pe_review.py .tmp/sqlite-runtime-r7-20261015/runtime/python/DLLs/_sqlite3.pyd .tmp/sqlite-runtime-r7-20261015/sqlite-official/sqlite3.dll > .tmp/sqlite-numpy-r7-review-20261015/pe-review.json`，exit0。检查器仅读取bytes/PE结构，不加载或执行被审DLL。

- 两个PE均Machine `0x8664`、PE32+；标准库`_sqlite3.pyd`的88个sqlite3命名imports全部出现在官方新DLL的379个命名exports，missing0。
- 新DLL SHA256 `5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656`。新DLL直接import descriptor仅`KERNEL32.dll`；不据此推断没有静态CRT或所有系统依赖已审。
- 原binding还直接依赖`python312.dll`、`VCRUNTIME140.dll`和UCRT APIsets，完整符号清单见私有`pe-review.json`。
- 本结果证明导出名称和架构匹配，不证明ABI行为、实际加载路径、完整CPython测试或无漏洞；最终runtime及真实I/O继续验收。

## 最终独立代码及行为复审

结论：**最小真实I/O与连接硬化条件通过，可保留为隔离派生候选**。0 Critical、0 High；2项Medium非阻断边界见下。初始设计3项细化已在最终实现及真实测试落实；完整adapter/Chroma where/生产原数值契约/完整生命周期、生产迁移与发布均未放行。原生公告逐项核对由root另外给结论，本评审不将pip-audit0写成原生0漏洞。

### 最终输入与实际验证

仅绑定新目录`docs/testing/sqlite-numpy-r7-final-20261015/manifest.json`，SHA256 `fcf0ecf3cbf8c5a57ceb98d970333a7c54f9de09ab5ec6951d2fcbfeab41fc2d`。评审者亲核45文件大小/摘要全部一致，复制source至私有`private-final/`，8执行输入前后摘要无漂移。最终store SHA256 `28cede24b74aaaad92ccd0c3ca327203f9e3648e8afbbadfe5d61b6870b750da`。

实际正规escalated离线命令：`.tmp/sqlite-numpy-r7-20261015/.venv/Scripts/python.exe -X utf8 .tmp/sqlite-numpy-r7-review-20261015/run_review.py`，退出0。runner在私有copy执行：

- `python -X utf8 -m unittest test_store -v`，exit0，9组全绿：真实CRUD/批原子性/持久化子进程/固定schema/参数注入/余弦边界/每连接硬化/backup身份与拒篡改/跨进程reader-writer锁超时及terminate回滚；backup小quota真实DB故障注入拒绝并清理目标，不影响原库。quota测试仅mock政策常量及read_bytes spy，不mock SQLite/native I/O。
- `python -X utf8 -m unittest test_independent -v`，exit0，2组全绿：新seed74101593，7维137记录、13查询，每次11top-k及有/无恶意source过滤，与独立`math.fsum`余弦参考排名完全一致，score小数14位一致；backup全部137条ID/source/text/metadata/向量逐项对账，删源后原库91条/恢复库137条相互隔离。另4线程各10条独立连接真实写读，40条完整，每连接配置与ATTACH拒绝核验通过。

日志及命令/elapsed/退出码/前后摘要见私有`review-receipt.json`、`author-nine.stderr.log`、`independent-new.stderr.log`。本轮无网络、真实供应商、生产数据、`.env`读取，不改产品或主锁。

亲读冻结identity：CPython3.12.15、实际base_prefix派生profile、SQLite3.54.0/source_id `2026-10-09 15:46:58 be8d059e9a49089ab2dce5ed26dd87aaf598fdc5fbe0b107c0dd758464bcd5e3`，NumPy2.5.4，锁唯一registry依赖与安装一致。安装绑定报告核948个带摘要RECORD文件；wheel字节未保留，仅uv frozen sync对锁及安装RECORD证据，不宣称亲核保留wheel ZIP。官方完整CPython＋替换SQLite官方DLL为项目派生组合，不承袭其官方整体支持/完整测试声明。

### 🟡 Medium — 接受大小上限不是分配前资源防护

位置：最终`source/store.py:64-70,126-137`。`np.asarray`与`json.dumps`先转换/分配，后核shape/bytes。当前受控Python调用合成域不阻断；不得宣称能防御任意超大Python对象或自定义`__array__`。未来暴露外部API需在转换前约束纯容器类型、长度、嵌套及请求bytes。

```python
# 当前（受控输入）：vector = np.asarray(value, dtype='<f8'); validate_shape(vector)
# 未来外部入口：validate_plain_numeric_sequence(value, dimension); vector = np.asarray(value, dtype='<f8')
```

### 🟡 Medium — search全量fetchall内存不等同小常量预算

位置：最终`source/store.py:160-178`。10000×4096×8仅向量载荷约312.5MiB，尚不含tuple/ID/数组/排序内存；有限记录范围不证明任何生产RSS或SLO。此原型未宣称分批低内存，受控小输入通过不解除生产规模门槛。

```python
# 当前：rows = con.execute(FIXED_QUERY, parameters).fetchall()
# 未来完整adapter：for rows in bounded_batches(cursor): update_bounded_topk(rows)
```

### 冻结过程限制

亲读新final的`archive-correction.json`：初版R7 `source/store.py`、`source/test_store.py`及manifest已被更新覆盖，原manifest bytes未保留，不能声称初版32项冻结未改，也不能声称完整重建。自动approval review拒绝恢复/重建旧证据操作，拒绝脚本未执行；未绕过。旧目录只作为历史诊断，本报告的最终正确性证据来自新final45项摘要核验及上述独立新命令。R5/R6其他旧冻结不在本次修改范围。

### 优先级

1. root完成精确原生身份与适用公告结论，并归档本评审脚本/收据/日志；保持整体支持与扫描范围限制。
2. 需要完整adapter时再按原权威契约处理分批/top-k内存、全部where/数值兼容、分页及应用生命周期验证，不能把该原型直接替换生产。
3. 若考虑外部输入服务化，先新增分配前输入资源预算及有效行为测试，再开放入口。

已审及已测，未提交/未集成/未部署。本轮未执行产品全量双90，不能沿用旧报告证明当前他人改动后的全树。
