# R4b 宽整数入口候选验证

仅隔离候选，生产替换仍 BLOCKED。未改产品、主锁、`.env`、原数据、output 或 Gold；无提交、推送、部署。

根因：r4 在标量及集合查询中人为拒绝绝对值超过 U64 的原始 Python int，而真实 Chroma 1.5.9 会把超 U64 的 JSON 整数经 serde_json 长整数路径解析为有限 f64。r4b 仅删除这两处幅度检查，沿用通用 stdlib parser port；不按数字特判、不依赖 Chroma runtime。正数在 I64 与 U64 之间仍保持 u64 并按旧入口拒绝；超 U64 值由解析器自然转为 f64；10^309 自然溢出拒绝。record 原始 int 仍要求 signed I64，Python json digit limit、有限数检查及原始同类集合检查均保留。

| 实际验证 | 结果 |
|---|---|
| 144 宽整数条件：known/unknown、六比较、in/nin、首类型逆序 | Chroma oracle exit0；Lance 红 exit1 差异72 → 绿 exit0 差异0 |
| 旧32宽整数探针 | 红差异16 → 绿差异0；真实oracle接受20、拒绝12 |
| 原76 / 44 / 162 | 五个子命令全部 exit0、零差异；保留64拒绝断言 |
| 原44消费者 | 9 cosine 排序/距离/score、持久 schema 恢复、7拒绝通过 |
| 原312 raw + 84入口错误用例 | exit0、成功ID及拒绝状态零差异；raw及compat值和类型核验 |
| 新seed141020264：128有限float + 6位级特殊值 | Chroma/Lance 128条件 exit0、零差异；raw与compat逐位读回（±0、±最小subnormal、±最大finite）通过 |

执行入口 `.tmp/vector-ingress-r4b-20261014/execute_r4b.py red` / `green`；Lance 使用 `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe`，Chroma 使用 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`。真实依赖命令经正规提升审批离线执行。`red-execution-manifest.json` 与 `green-execution-manifest.json` 保存 UTC、命令、退出码和执行前后源码哈希；final/manifest.json 保存原矩阵五子命令及输入哈希。红证据保留，最终冻结前重复全部 green 验证。

冻结目录 `vector-ingress-r4b-20261014/`，`freeze-manifest.json` 记录逐文件 SHA256、最终已测试源码核验以及旧 r4 81 文件无漂移检查。复制来的历史 `archive.py` / `finalize.py` 指向旧归档，顶层副本排除冻结，`final/` 下的历史嵌套副本保留在冻结中；两者均未执行。r4b 仅用 `freeze_r4b.py`，不能覆盖旧冻结。

剩余限制：异常类/消息未映射，候选 ValueError 与 Chroma InvalidArgumentError 保留各自真实类型，公共adapter错误兼容仍 OPEN。全 binary64 formatter 与 Zmij 等价未证明；本轮只证明实际测试域。全adapter、安全扫描、迁移、并发恢复、全量双90均未在本轮执行，不能据此关闭整体 H2 或声称可生产替换。

收尾复验：root核110新文件及旧81文件hash后私有复制，实际重新执行全部green五子命令exit0（原矩阵内五子命令也全部0），27份日志/清单保存[复制复验](vector-ingress-r4b-rootverify-20261014/manifest.json)。独立reviewer静态审未发现新增阻断，另seed202610141731的9226项Rust parser差分及真实Chroma/Lance新128条件均零差异exit0；原76/44/162等全套由root复制复跑，不能称为reviewer全套重跑。见[独立复核](../review/2026-10-14-vector-ingress-r4b-review.md)，9份独立脚本/回执/结果已核hash并保存[独立证据](vector-ingress-r4b-review-20261014/manifest.json)。110原freeze未修改；H2仍为部分修复。
