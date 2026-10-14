# 向量替换 r2 独立审查

2026-10-14；审查范围为设计与隔离合成探针，不涉及产品集成。master / `46b202c3e400741fd569f024412c0745f224a538`，工作区其他任务改动保留。最终冻结独立复验完成。

## 审查总结

动态metadata安全编号、持久化同代mapping、presence/type/value谓词方向正确；独立复跑确认原76项零差异、新44项中4差异和9组cosine消费者断言通过。问题统计：1 High开放；1 Medium证据缺口已关闭。有限大float过滤新增拒绝仍阻断直接替换；本轮保留真实FAIL，不声称已修复或全面兼容。

## 问题清单

### 🟠 High H1：合法大float被int64转换拒绝（OPEN）

位置：`.tmp/vector-replacement-mvp-20261013/r2/generic_filter.py`，第52–59行，`_scalar` 数值转换分支。

现实现为全部数字查询先执行 `int(value)` 并检查signed int64，超界直接ValueError，连已存在float记录也不能比较。独立 `extreme_oracle.py` 对真实Chroma 1.5.9合成int1/float1.5执行±1e30的eq/ne/lt/gt八例均成功，证明新增拒绝确实不兼容。命令使用独立后端质量环境，正规require_escalated执行，exit0；不import backend。

```python
# before
integer = int(value)
if not -(2**63) <= integer < 2**63:
    raise ValueError('query conversion exceeds tested int64 boundary')
# after（后续设计要求，当前未实现）
# float记录维持旧库实证谓词；超界literal对int记录必须先固定旧库转换真值。
# number > -1e100在Chroma中排除int64.min，不能猜测数学常量true。
# 再泛化实现并独立复验，不缩合法输入、不按夹具特判。
```

### 🟡 Medium M1：消费者探针使用L2，不能支持cosine契约（CLOSED）

位置：`r2/boundary_probe.py`，`vector_checks`。

过滤后L2排序能说明prefilter返回足量，但产品设计使用cosine及分数映射。建议显式cosine并用独立NumPy公式核过滤集合内完整top-k与距离/分数；无匹配、k超过集合均保留。

最终`boundary_probe.py`第72–85行已采用cosine+NumPy完整过滤集合参考，9组ID精确一致、距离atol2e-7、score atol1e-7独立重现。早期L2历史仍独立保留；这里只关闭该局部证据缺口，不证明所有向量输入或完整适配兼容。

```python
# before
search(query).distance_type('l2')
# after
search(query).distance_type('cosine')  # 对独立cosine参照核对
```

## 静态核对与范围限制

- key只映射为内部m编号列，原始键与字符串经literal/JSON存储，不拼SQL标识符；中文、引号和类似注入文本是数据。
- 存在位和真实标量类型分别持久化；int64与float64分列，不能用cosine容差替代metadata整数精度。未知键只有完整同代mapping可证明missing；新键encode显式拒绝，不冒充schema演进已实现。
- depth/width/共享AST节点预算存在；in/nin展开literal未计入512节点，但受64成员及AST预算约束。资源上限属于探针新增约束，未获接受的公共契约不得称兼容。
- oracle仅比较OK/REJECTED与ID集合，未核稳定错误类别、文案或全部非法形状。固定静态generation不等于完整适配、增量回填、全局屏障或生产消费者通过。

## 阶段1和原生安全边界

40文件阶段1manifest SHA256 `2d823ba78b78574e7a95680257a498c80501f150cffb8c0841be34ae3f131d23` 本次逐文件尺寸/hash核实0漂移，shell exit0，收据 `.tmp/vector-r2-review-20261014/stage1-hash-verification.json`。原12项原生能力通过、18过滤case五差异保持冻结；本次未重复这些测试。

设计SHA256 `0f090064d17ea58edc0a97b19f8e70c783dbcbbaf4d1352095ec960268127f9d` native补充已定点复核。独立访问[SQLite官方CVE页](https://sqlite.org/cves.html)核修复版本及SQL/恶意DB/FTS5与defensive前提：运行3.45.3低于多项修复，但版本比较不等于本应用可利用。17项PyPI审计零公告不覆盖SQLite运行DLL、Lance Rust、Arrow及wheel内原生依赖。完整SBOM与部署入口可达性未完成；文档正确保留安全未清零边界，无新增设计阻断。

## 优先级

1. H1保持开放：后续先补超界literal×记录类型×端点×操作符真值设计，确认后只重开numeric分支；本轮评估以失败边界交付。
2. 最终冻结与独立复跑已完成；保持M1关闭和所有实际FAIL，不以归档成功退出码替代测试退出码。
3. 按设计补选型必要证据；完整adapter、增量schema、固定G分页/全局快照、崩溃、迁移及真实消费者仍NOT_RUN。未修改产品/主锁/原数据/Gold，无commit/push/deploy；负责人负责memory汇总。

## 最终冻结与独立执行证据

冻结manifest SHA256 `bcdbf857cb1bd0f4cf658390a62387bb3545e9a7bc07ce4378485ecd5170a5cf`，38文件逐项hash核验无漂移。复制脚本/fixture字节与冻结输入相同；compiler SHA256 `cf45530dd8eab3013fb86f9c180bd2919300f2747893f721c1621c3bb5066f95`，boundary脚本SHA256 `d19dda4d65841ec4c586fd4e7d1c8b7747216665db701cdf03e13327dce44087`。

下列命令在`.tmp/vector-r2-review-20261014/`执行，只写review独占合成库，真实候选进程均正规`require_escalated`，无绕审批：

| 命令 | exit | 独立结果 |
|---|---:|---|
| 候选`.venv/Scripts/python.exe lance_truth.py` | 0 | 76项零差异 |
| 质量环境`Scripts/python.exe boundary_probe.py chroma` | 0 | 44项真实oracle |
| 候选`.venv/Scripts/python.exe boundary_probe.py lance` | 1 | 44项中4差异；9cosine断言通过，7拒绝检查通过 |
| 候选`.venv/Scripts/python.exe finalize.py` | 0 | 冻结38文件无漂移，两份boundary报告与冻结JSON完全相同 |

完整log/exit、结果JSON及`final-review-receipt.json`在review独占tmp。两份boundary报告完全相同意味着反例也独立重现：`number > -1e100`排除了int64.min，饱和转换仅为待验证假设，不能直接当实现依据。大float纯float字段也被拒绝，不能把问题限定成int端点。新增设计顶部结论hash `d1a9c8b28d60c3f6cba15a136aa9be3504af2c125a8df67d1c4a544c85d967de` 定点核对准确；native安全段未变。

最终结论：**静态generation有界证据已独立确认，完整兼容仍BLOCKED；否决直接产品替换。** 本次没有复跑无变动后端全量，也不产生新的双90或生产集成完成声明。
