# 数值转换合同及 r3 修复独立审查

2026-10-14，master / 46b202c；仅审查隔离候选及数值合同。产品、主锁、原数据、旧冻结未修改。采用 requesting-code-review 的独立上下文与证据闭环要求。

## 审查总结

finite float→i64 截断饱和的局部合同与实现通过独立审查及真实依赖复跑，旧 H1 关闭。统计：1 High 已关闭、1 High 保持开放；原始 float 入/查询解析及超界原始 int 兼容未解决，完整替换仍 **BLOCKED**。

## 问题清单

### 🟠 High H2：原始数值入口与范围外整数兼容（OPEN）

位置：`docs/contracts/2026-10-14-vector-numeric-semantics.md`入口误差及错误章节；`.tmp/vector-numeric-r3-20261014/generic_filter.py` 第45行。

独立 Chroma 复跑重现原始模型76差异、4处readback漂移：r13/r15 的 number/float_only 在 add 后由 ±9.223372036854775e18 变为 ±9.223372036854776e18。官方 sqlite_metadata.rs 614–615 是 i64/f64 cast，不能据碰撞宣称 f32 索引。经验 readback 归一化312项一致只解释现有样例，不能作为编译器查表算法。候选精确保存原始binary64与旧库完整链仍有区别。

旧库原始 int `2^63` 被拒绝，但 `-2^63-1` 被接受；候选拒绝全部超I64 int是明确能力限制，不能称与Chroma错误契约一致。±inf/nan和未知key上的拒绝已复验，但错误类/消息完全一致未获证明。

```python
# before：禁止采用的推论
# raw Python float == Chroma parsed float
# after：正确边界
# compare(stored_record, parsed_query) 与 ingress(raw_input) 分层核验。
# readback经验模型只保存证据，产品替换维持BLOCKED。
```

建议继续定位入/查询解析链，分别保留原始输入、实际存储、查询解析、返回payload与过滤结果；不以删除反例、经验查表或f32假设关闭H2。

### 🟠 High H1：合法有限大float被拒绝（CLOSED，局部）

位置：`.tmp/vector-numeric-r3-20261014/generic_filter.py` 第45–58行；旧r2第52–59行。

旧实现无条件int转换及范围拒绝，导致±1e100连纯float字段也拒绝。r3按literal原始类型区分：I64 int精确保留，finite float对int记录向零截断并饱和，float记录保留float分支；验证在unknown key短路之前。六比较及in/nin共用_scalar，无fixture ID、key、特定float或真值查表特判。

```python
# before
integer = int(value)
if not -(2**63) <= integer < 2**63:
    raise ValueError('query conversion exceeds tested int64 boundary')
# after
integer = value if tag == 'int' else min(2**63-1, max(-(2**63), math.trunc(value)))
as_float = float(value)
```

修复未把超界比较变为数学常量；`number > -1e100`仍排除int64.min，负小数向零截断。I64端点不经float中转，metadata往返核值及类型，cosine容差仅用于向量结果。

## 最终快照与独立执行证据

冻结目录`docs/testing/vector-numeric-r3-20261014/`，manifest SHA256 `ada19b666076f4f7f2dfda0557c176d8ea4b39d16709a098b117dc29e87344f6`；61冻结文件hash零漂移。compiler SHA256 `ebbff5e75703a5a9a5ea6014be0c7d85a1b9904e13029743c2145bd3f772e92a`。复制脚本/fixtures与green输入逐字节一致，green记录的合同/锁/输入hash再次核对无漂移。

命令在review私有目录执行，真实原生进程均正规require_escalated离线执行，无provider/.env。质量解释器`.tmp/backend-quality-venv-20261012/Scripts/python.exe`，候选解释器`.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe`：

| 解释器及脚本 | exit | 独立结果 |
|---|---:|---|
| 质量 `probe.py` | 0 | 真实Chroma1.5.9，312经验模型一致、84错误边界；除OUT/script hash外oracle与冻结完全相同 |
| 候选 `lance_truth.py` | 0 | 原76项零差异 |
| 质量 `boundary_probe.py chroma` | 0 | 44项真实oracle |
| 候选 `boundary_probe.py lance` | 0 | 44项零差异；9cosine消费者、7拒绝及同代mapping/精确metadata断言通过 |
| 质量 `numeric_matrix.py chroma` | 0 | 162项稳定输入域真实oracle |
| 候选 `numeric_matrix.py lance` | 0 | 162项零差异；80项候选能力拒绝单列 |
| 质量 `finalize_review.py` | 0 | 61文件hash、green输入、四份boundary/matrix报告JSON完全一致 |

`.tmp/vector-numeric-review-20261014/`保存实际log/exit、合成库、oracle与final-review-receipt.json。312模型永久7文件也独立核hash零漂移。80候选拒绝不算旧库全域兼容通过。

## 优化建议汇总

1. H2继续阻断整体替换，下一步定位入/查询解析链及超界原始int策略，保留全部红证据。
2. H1局部关闭，保持冻结；合同/源码/fixture变化后重新核受影响消费者。
3. 完整adapter、迁移、增量schema、全局快照、崩溃恢复、真实生产消费者、安全清零仍未验证；本次局部回归不替代选型与整体验收。

未执行无改动产品全量或新双90；无提交、推送、部署。负责人统一更新memory。
