# KG 版本保留修复专项证据

日期：2026-10-13。仅覆盖版本生命周期修复，不替代完整后端双覆盖率、安全扫描或独立评审。不提交、推送或部署，不读取 `.env`，不触碰用户 `output`、研究冻结或其他 Agent 的图索引修改。

## 问题与最终协议

独立评审发现 12 个目录 v0..v11、manifest active_version=0 时清理仍选择活跃 v0。缺失或损坏 manifest 时同样猜测删除；旧创建器用列表长度分配 ID，清理列表后会复用 ID；旧激活器只看列表，可激活已经不存在的版本目录。

- 创建、激活及清理共享每文档 `.versions.lock` 真实 FileLock，读取 manifest 和选择清理候选均在锁内重新执行，预览不作为执行授权快照。
- 只识别规范目录 `v0` 或 `v[1-9][0-9]*`，保护 manifest 中已知且存在的 active_version，保留活跃版本及最新九个非活跃版本；未知活跃、缺失/损坏/结构非法 manifest 均拒绝清理。文档及候选 resolve 必须位于 KG 根内。
- 创建使用 manifest `next_version` 高水位、manifest 历史条目及磁盘最大 ID，且 mkdir 不允许覆盖已有目录。manifest 使用同目录临时文件、flush/fsync、os.replace 原子替换。激活拒绝不存在目录、symlink、junction 及越界路径。
- 清理先计算高水位，再将候选 rename 为同目录 `.retired-vN-<随机标识>`；原子提交 manifest 去条目及高水位，写失败完整 rename 恢复，最后 rmtree 隔离目录。物理删除失败显式记录 `kg_version_cleanup_quarantined` 并保留隔离数据，不重新暴露可能残缺版本。
- `_clean_kg_versions()` 返回已提交的 **logical_removed** 数量；该数量不证明物理空间释放。隔离目录未回收空间会继续体现在存储统计中，本轮不增加隔离垃圾自动回收协议。

协调者明确接受此事务协议，并负责 filelock 直接依赖及权威规范回流。本次只修改 `kg_store.py` 版本管理段、`services/lifecycle.py` KG 版本段、独立回归测试及 `test_service_readiness.py` 中 KG 版本 fixture/相关断言。其他清理类别不变。

## 红绿及验证

执行器：`.tmp/backend-quality-venv-20261012/Scripts/python.exe -B`；环境 `PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`PYTHONUTF8=1`。下表命令均为该执行器后接 `-m pytest`。

| 范围、basetemp | 结果 |
|---|---|
| `backend/tests/test_lifecycle_retention_readiness.py -q --basetemp backend/tests/_sandbox_tmp/kg-retention-red` | exit1，10 failed，真实复现活跃误删选择、未知 manifest 不拒删、非法目录计入及不存在版本可激活。 |
| 同专项，`kg-retention-green1` | exit0，10 passed。 |
| 专项 + `test_kg_store_quality_behaviors.py`，`kg-retention-green2` | exit0，63 passed；真实进程间锁三操作、线程 barrier、manifest 写失败恢复、物理失败隔离、孤立目录不覆盖均已验证。 |
| 同两文件，`kg-retention-green3` | exit1，67 passed / 1 failed；真实 junction 创建被沙箱 Access denied 拒绝，不能算功能通过。 |
| 同两文件 + `test_service_readiness.py`，`kg-retention-green4`，获准沙箱外 | exit0，91 passed，真实 junction 越界 sentinel 未改变。 |
| 专项 `-k directory_links`，`kg-retention-activate-red`，获准沙箱外 | exit1，1 failed / 22 deselected；真实 Windows junction 被旧消费者成功激活，复现后补激活拒绝。 |
| 三文件，`kg-retention-final`，获准沙箱外 | exit0，91 passed。 |
| 专项 `-k invalid_highwater`，`kg-retention-highwater-red` | exit1，1 failed / 23 deselected；无效 next_version 在 rename 后报错，v1 不再可见。 |
| 同选择，`kg-retention-highwater-green` | exit0，1 passed / 23 deselected；计算移至 rename 之前。 |
| **最终三文件**，`kg-retention-final2`，获准沙箱外 | **exit0，92 passed / 6.41s**，JUnit 见下。 |

最终完整命令：

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -m pytest backend/tests/test_lifecycle_retention_readiness.py backend/tests/test_kg_store_quality_behaviors.py backend/tests/test_service_readiness.py -q --basetemp backend/tests/_sandbox_tmp/kg-retention-final2 --junitxml docs/testing/2026-10-13-kg-retention-junit.xml
```

JUnit：[92 项机器报告](2026-10-13-kg-retention-junit.xml)。测试组合存在重叠，不能将各轮 passed 相加为全量数。本专项没有生成覆盖率指标或声称达到双90；协调者须对最终合并快照重新运行固定完整生产分母覆盖率和安全扫描。

静态检查：`python -B -m ruff check backend/kg_store.py backend/services/lifecycle.py backend/tests/test_lifecycle_retention_readiness.py` 实际 exit0、All checks passed；`git diff --check -- backend/kg_store.py backend/services/lifecycle.py backend/tests/test_lifecycle_retention_readiness.py backend/tests/test_service_readiness.py` 实际 exit0。Windows 是 audit-only-windows，不代表可信 CI 已启用。

## 最终验证输入 SHA256

```text
backend/kg_store.py 675ea9ec73223bf5a87b7f60e2b4935ef153f130159b278bdf00698b7b3e6879
backend/services/lifecycle.py 2c5087d241ae742392013d71c2fe80bbe69d9a5473b9d6e6f31975fa1abb21d8
backend/tests/test_lifecycle_retention_readiness.py ab0fb5c41c3aeb1d1c694d4d52a62dcb20f235f762e46f0d15112504a34631f3
backend/tests/test_service_readiness.py f96ab7057d209a8ddef5e663c7e4662b04862fb2c3b9b3446607f9747c18e903
```

后续：协调者更新权威规范及 memory，独立 reviewer 复核消费者、锁、事务边界及测试质量；然后完整最终验收。物理回收失败可能留存隔离目录；本轮保证安全保留和不可激活，不虚称释放存储。进程崩溃后的隔离残留运维回收尚无自动协议；本测试验证函数返回/异常路径，并未模拟断电持久性。
