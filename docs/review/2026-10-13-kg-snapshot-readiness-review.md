# KG 保留与运行快照独立复核

## 审查总结

原 High「清理误删已激活旧版本」在本次局部范围可关闭：共享真实 FileLock、锁内重新选候选、active 加最新九个非活跃版本、rename 隔离及 manifest 写失败恢复均有有效行为证据。运行快照改用完整 export_rows，独立真实 6001 行核验无截断，失败不会用空数据覆盖原件。新增 Medium 1 项仍开放；Critical 0、High 0 开放、Low 0。不构成全量双覆盖率、安全扫描、提交或部署许可。

遵循 AGENTS → memory/index.md → 今日记录及当前 readiness/retention 报告。using-superpowers 的 SUBAGENT-STOP 适用于本任务；已读取 requesting-code-review 并适配其独立评审原则，不递归派发、不启用 goal/Harness/state。分支 master，HEAD 46b202c3e400741fd569f024412c0745f224a538。仅拥有本报告，不改源、测试、冻结或其他任务文件。

## 问题清单

### 🟡 Medium：非整数高水位没有在破坏性操作前拒绝

- 文件：`backend/kg_store.py` 行 329–333、352–372；`backend/services/lifecycle.py` 行 234–271。
- 描述：版本条目和 active 使用严格整数检查，但 `next_version` 未校验类型。独立临时 manifest 设置 `next_version=99.5`，实际清理删除两个版本，随后 create 返回 99.5、创建 v99.5 并设 active=99.5；activate_version(99.5) 返回 False。非规范版本不再被清理枚举，active 非整数导致后续清理拒绝。损坏元数据应 fail closed 的协议未完全实现。现有 invalid_highwater 测试只测字符串，没有覆盖浮点/布尔等结构异常。
- 建议：在任何 rename 或 mkdir 之前统一校验存在的 next_version 为严格 int 且 >=1；异常抛 ValueError，清理拒删、创建不写数据。缺字段继续兼容旧 manifest，并以历史与磁盘最大值补高水位。追加真实 float/bool/负数/空值行为断言。

```python
# before
return max([0, meta.get("next_version", 1) - 1, *history, *disk]) + 1
# after (示意，未落地)
highwater = meta.get("next_version", 1)
if type(highwater) is not int or highwater < 1:
    raise ValueError("invalid next_version")
return max([0, highwater - 1, *history, *disk]) + 1
```

## 已核实行为与测试质量

- 版本操作在同一 `.versions.lock` 下执行，真实子进程持锁对 create/activate/cleanup 均阻断；线程 barrier 检查唯一 ID、磁盘/manifest 一致性；清理执行不信任旧 preview。
- active=0 保留；缺失、损坏、未知 active 元数据拒删；非法目录名不计入；高水位包含历史/磁盘孤立目录，失败创建不会复用并覆盖孤立目录。
- manifest replace 失败完整恢复目录及原 manifest；物理删除失败留存隔离数据、从可激活 manifest 移除。逻辑删除计数不代表释放磁盘。真实 Windows junction 越界 sentinel 和目录均保留，激活拒绝 junction。
- 当前 TableIndex/RestoredTableIndex 均实现完整 export_rows。真实 DuckDB 插入 6001 个唯一行后 snapshot 长度和恢复 export 长度均为 6001；连接关闭导致 export 失败后 snapshot 返回 None，原字节不变。旧 query 签名仍兼容，其 5000 fallback 不是当前两个生产类的快照路径。
- conftest 逐例设置运行产物环境变量及模块路径，reload 后保持隔离。新测试断言真实持久化结果和原件 hash，未以 mock 代替快照行为。未发现本范围减少生产覆盖分母、降低阈值、忽略分支或削弱原有效断言；本复核未生成覆盖率，不能据此声称双90达标。

## 独立验证

环境：`.tmp/backend-quality-venv-20261012/Scripts/python.exe -B`；PYTHON_DOTENV_DISABLED=1、HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1、PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1。未读 `.env`、用户正文或调用模型。

```text
-m pytest backend/tests/test_lifecycle_retention_readiness.py backend/tests/test_kg_store_quality_behaviors.py backend/tests/test_service_readiness.py backend/tests/test_runtime_artifact_isolation.py backend/tests/test_runtime_recovery.py backend/tests/test_parser_index_readiness.py backend/tests/test_table_security_readiness.py -q --basetemp backend/tests/_sandbox_tmp/review-kg-snapshot-20261013-02
```

- 同组合 basetemp `review-kg-snapshot-20261013-01` 在沙箱内 exit1：真实 junction 权限拒绝及 asyncio socketpair accept 超时，不能算通过。
- 上述 `-02` 获准沙箱外执行：**178 passed / 14.24s / exit0**。没有将各轮或作者 92 项累加为全量数。
- 独立 6001 行及连接关闭失败保留探测 exit0。首次输入遗漏 DuckDB 必填 row_id 导致探测 exit1，修正探测输入后执行成功，未更改源码。
- 独立非法浮点高水位探测真实复现问题；其命令末尾的大表错误导致整体 exit1，不把它记为测试通过。

### 产物保护与一次探测副作用

backend/output/runtime 前后仅读取 hash：bm25 `167db23567a6f8b5a5de52f4011fac21ff1858e5fc8c18b30b73f02a59c3dee0`、table `43f7ce0b32bcf9c2d942403676d2f4a382fddcbe4967662e58231bb73415e12c`，均未变化。table 与恢复收据一致；未改历史 freeze，未重新读取原文。

非法高水位临时探测遗漏 chdir：KG 数据在 `_sandbox_tmp/invalid-highwater-*`，但 create_version 事件/审计使用相对 output，于 16:46:00 向仓库根 `output/events/events-2026-10-13.jsonl`、`output/audit/audit-2026-10-13.jsonl` 追加诊断记录。已立即报告协调者，未读取正文、删除或擅自回滚。故**不能声称所有用户产物前后无变化**；后续快照探测已先 chdir 独立临时目录。本报告不隐瞒此副作用。

验证快照 SHA256：

```text
backend/kg_store.py 675ea9ec73223bf5a87b7f60e2b4935ef153f130159b278bdf00698b7b3e6879
backend/services/lifecycle.py 2c5087d241ae742392013d71c2fe80bbe69d9a5473b9d6e6f31975fa1abb21d8
backend/index_registry.py 4406c4234a262b099447751d3f7b3ea3c441a49f28934045eb4ad8d978262b93
backend/table_index.py fa9ff038fe21ad71597982a15afa0137a9dd6072f7c57b25f610b77bfd620297
backend/tests/conftest.py b4883b1f062ffc59d30aeb26803a88f308573dd66a14db7f49398022c97a9539
backend/tests/test_lifecycle_retention_readiness.py ab0fb5c41c3aeb1d1c694d4d52a62dcb20f235f762e46f0d15112504a34631f3
backend/tests/test_runtime_artifact_isolation.py e110d2a960842c1a768358b3e986a558848c15bf1ba063dd9fdb4bf1ef4362ab
```

## 优化建议汇总

1. 修复严格高水位校验并独立复验；修复后重新绑定专项证据。
2. 协调者核实并记录诊断日志副作用，规范及 memory 回流由协调者完成。
3. 最终合并快照执行固定完整生产范围双指标及漏洞扫描；研究漂移继续阻断，不提交、推送或部署。Windows 仍为 audit-only-windows。
