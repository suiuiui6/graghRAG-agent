# R3 隔离数值谓词局部修复

结论：合同支持子域的饱和转换缺陷 H1 已修复并完成本地回归；原始 Python float 入口漂移 H2 仍 OPEN，整体生产替换仍 BLOCKED。未修改生产代码、主依赖锁、旧 r2 冻结、.env、output 或研究 Gold。无提交、推送、部署。

依据：[数值合同](../contracts/2026-10-14-vector-numeric-semantics.md)。仅修改独立 r3 `generic_filter.py`：float 查询的 int 分支采用 `clamp(trunc(q), I64_MIN, I64_MAX)`；float 分支仍比较原始 q；I64 int 查询精确保留，越界 int 明确拒绝。literal 验证先于未知键短路。没有 readback 查表、f32/舍入模拟或夹具特判。

## 实际验证

完整命令、UTC、退出码和输入前后 SHA256 位于 `vector-numeric-r3-20261014/{red,green}/manifest.json`；文件 SHA256 位于 `freeze-manifest.json`。真实 Chroma 1.5.9 与 Lance 0.40.0 使用已有独立锁定环境，显式合成向量，不读取 .env 或调用模型。所有数据库仅在 `.tmp/vector-numeric-r3-20261014/`。

实际执行入口（仓库根，正规 require_escalated 离线运行）：

```powershell
& .tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-numeric-r3-20261014/run_checks.py red
& .tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-numeric-r3-20261014/run_checks.py green
```

| 项目 | 修复前 | 最终修复后 |
|---|---|---|
| 原 76 差分 | exit 0，零差异 | exit 0，零差异 |
| 原 44 边界 | Lance exit 1，原四项失败 | 两依赖均 exit 0，零差异 |
| 新 162 稳定 literal 条件 | Lance exit 1，44 差异 | 两依赖均 exit 0，零差异 |
| 额外候选能力边界 | 64 拒绝、16 未拒绝 | 80 拒绝全部满足 |

red 入口实际 exit 1；green 入口实际 exit 0。新矩阵覆盖三个 key（混合 number、float_only、unknown）×八个查询值×六操作，加三组 in/nin：I64 精确端点及邻接 int、±1.5、±1e100；记录含 bool/missing 与极大 float。80 个拒绝断言覆盖 known/unknown 的超 I64 int、非有限 float 与六操作/in/nin；这是候选能力限制，不声称 Chroma 错误类完全一致。特别是 Chroma 接受 `I64_MIN-1`，候选明确不支持。

原 44 脚本完整保留并复跑：9 组 cosine prefilter top-k 精确 ID 排序与 score、7 项资源/encode 拒绝、fresh connection 从持久 schema 恢复 mapping、metadata 精确值和 Python 类型往返均通过。向量浮点容差仅用于距离/评分，不用于 metadata 判断。最终快照输入前后 hash 一致，归档时再次核对 green 输入。

## 保留边界

此矩阵主动限定到真实 oracle 已验证的稳定 literal 子域。未将原始 312 条件中的 76 个入口漂移差异改为通过；完整 raw 模型失败证据保留在 `vector-numeric-semantics-20261014/raw-model-differences.json`（以该目录实际清单为准）。同域谓词转换成立不证明任意 Python binary64 的原始入口兼容。

完整 adapter、增量 schema/backfill、全局快照与并发崩溃、100K 扩测、native 安全问题、生产迁移及全量双 90 门槛均未在本任务执行。最终冻结交独立 reviewer 复跑；本报告不能替代独立复核或生产验收。

