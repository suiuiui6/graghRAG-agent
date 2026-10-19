# SQLite＋NumPy R7 隔离运行库验证

状态：作者、root 复制复验及独立最终评审均已通过，允许作为隔离开发候选。按已通过条件的[计划](../plans/2026-10-15-sqlite-numpy-runtime-validation.md)执行；实现仅限固定 schema、有界精确余弦原型，无生产集成或 Chroma 全过滤兼容声明。

## 最终核验与永久证据（2026-10-15）

root 对最终45文件逐项核摘要后，在私有复制源码上运行 `python -B -X utf8 -m unittest -v test_store`，9项通过、exit0、输入摘要无漂移，见[实际命令与收据](sqlite-numpy-r7-rootverify-20261015/root-receipt.json)。独立评审另复跑作者9项及独立2项，均exit0；新增137条记录×13查询的独立排序/得分、备份全量对账、4线程各10次独立连接写读与硬化检查通过，见[独立收据](sqlite-numpy-r7-review-20261015/review-receipt.json)及[评审结论](../review/2026-10-15-sqlite-numpy-runtime-review.md)。这些是专项行为验证，不能替代生产全量覆盖率。

运行库来源及原/派生全树摘要见[永久运行库归档](sqlite-runtime-r7-20261015/archive-manifest.json)。测试后再次核验原始与派生profile，均无新增或内容变化；派生与原始之间唯一预定差异为 `python/DLLs/sqlite3.dll`。GitHub官方Python资产摘要是来源权威，npmmirror仅作下载传输；提取前已匹配官方SHA256。SQLite DLL来自官方压缩包并核对官方SHA3-256。该组合是项目派生profile，不继承完整官方发行版回归或支持保证。

新环境实际只安装锁定的 NumPy 2.5.4。root 新执行 `pip-audit --no-deps --disable-pip --strict --index-url https://pypi.org/simple` 审计精确单依赖清单，exit0、已知包公告0，见[安全核对归档](sqlite-numpy-native-r7-20261015/archive-manifest.json)。这不等同原生漏洞清零：CPython全组件、OpenBLAS全公告、Windows CRT完整SBOM/安全扫描未执行。实际NumPy构建内OpenBLAS为0.3.34.106.0；来源政策与版本核对仅覆盖已查公告。

剩余优先级：P0在开放外部API前前置输入形状/尺寸限制，并将查询全量fetchall改为有预算的分批评分；P0完成完整VectorStore及Chroma metadata/where/formatter契约差分和生命周期恢复验证；P1补原生组件清单、受支持运行库更新策略及性能/规模验证。生产替换前仍需适用真实依赖集成、全量双90及漏洞扫描。本轮未提交、推送、部署或迁移，现役Chroma四项公告未被此原型消除。

作者文件范围为 `.tmp/sqlite-numpy-r7-20261015/` 和本报告及同名证据目录；其他任务生产改动、主锁、旧环境、旧冻结及真实数据均保持。

已准备 `unittest` 行为测试，覆盖真实批写事务/重复 ID 回滚、参数绑定特殊字符、读删及新进程重开、余弦得分 1/.5/0、source 预过滤、ID 稳定并列排序、top-k 边界、有限非零数值/极端尺度、快照身份与失败恢复、逐连接硬化及真实多进程读/写锁超时/事务中止。

运行库为 root 核验的项目新派生 profile `.tmp/sqlite-runtime-r7-20261015/derived/python/python.exe`，不是未修改官方完整构建。实际 Python 3.12.15、SQLite 3.54.0、OpenSSL 3.5.9；SQLite source_id 为 `2026-10-09 15:46:58 be8d059e9a49089ab2dce5ed26dd87aaf598fdc5fbe0b107c0dd758464bcd5e3`。原官方构建 SQLite 3.53.1 的 floor 红证据由 root 保留；派生输入及组合边界见 root 的 `derived-composition.json` 和 `derived-evidence/runtime-native.json`。本作者没有更改源/派生 DLL，每次运行设置 `PYTHONDONTWRITEBYTECODE=1` 并传 `-B`。

实际顺序及命令结果见[冻结清单](sqlite-numpy-r7-final-20261015/manifest.json)，完整命令、时间、源码/锁摘要及 stdout/stderr 位于各标签 JSON/log：

| 标签 | 实际结果 | 范围 |
|---|---|---|
| `red-stub` | exit 1，8 errors | 明确未实现 stub 导致测试初始化异常；保留该首次证据 |
| `red-behavior` | exit 1，8 failures | 将同一未实现异常转为测试断言失败，确认缺功能后才实现 |
| venv 创建 | exit 0 | `uv venv .venv --python <精确derived/python.exe> --no-python-downloads`，项目私有 UV_CACHE_DIR |
| `uv-lock` | exit 0 | 精确单依赖 NumPy 2.5.4；source_drift=true 为首次生成 uv.lock 的预期结果 |
| `uv-sync` | exit 0，source_drift=false | `uv sync --frozen --no-python-downloads`；仅安装 NumPy |
| `green-initial` | exit 0，8 tests/2.597s | 全部作者行为测试 |
| `runtime-identity` | exit 0，无源码漂移 | SQLite/NumPy 构建、可见原生文件和实际已加载 Windows DLL 摘要 |
| `lock-check` | exit 0，无源码漂移 | `uv lock --check --offline --no-python-downloads` |
| `green-final` | exit 0，8 tests/2.543s，无源码漂移 | 最终作者源码快照全部行为测试 |
| `freeze` | exit 0，无源码漂移 | 安装仅 NumPy 2.5.4=锁依赖；948 带摘要 RECORD 文件独立校验，32 文件归档 |
| `red-backup-budget` | exit 1，1 failure，无源码漂移 | 真实小 SQLite 备份，将预算注入为1 byte，spy 观察发现先 read_bytes 后判断；是策略故障注入，不冒称原生模拟 |
| `green-budget-final` | exit 0，9 tests/2.691s，无源码漂移 | 增加 stat 预检及 MAX_SNAPSHOT+1 有界读取后的全部实际测试 |
| `freeze-budget` | exit 0，无源码漂移 | 948 RECORD 再验证；当前最终来源以此源码及 green-budget-final 为准 |

最终独立归档为 `docs/testing/sqlite-numpy-r7-final-20261015/`，45 文件，manifest SHA256 `fcf0ecf3cbf8c5a57ceb98d970333a7c54f9de09ab5ec6951d2fcbfeab41fc2d`。所有最终源码逐 hash 与 `green-budget-final.json` 的 source_after 匹配。

归档纠正：新 final 目录指示到达前，`freeze-budget` 已覆写初版 `sqlite-numpy-r7-20261015/source/store.py`、`source/test_store.py`、`manifest.json`；历史命令日志未改，R5/R6 未动。初版目录只能视为历史诊断，不能声称原32项冻结仍完整未变。自动审批拒绝了重建初版的脚本（理由是会修改/删除既有 baseline）；该脚本未执行，未绕过。随后仅复制当前真实修后证据到新 final 并生成[操作纠正收据](sqlite-numpy-r7-final-20261015/archive-correction.json)，没有再改旧 baseline。原始 manifest 字节未保留，不伪称已恢复。

源码副本位于[证据源码目录](sqlite-numpy-r7-final-20261015/source/store.py)。原型固定小端 f64、1–4096 维；每批及 k 1–1000、最多 10000 记录、1MiB 单记录预算、100MiB 快照预算。每个创建/读/写/备份/恢复连接都设置并核 defensive=true、trusted_schema=false、extension=false、foreign_keys=true、资源限额；不对外暴露 SQL。原型拒绝零向量及非有限输入，缩放归一化支持极大/极小有限非零数值。得分 `(cosine+1)/2`，有限性验证后只修正舍入尺度的区间越界；并列按 ID 升序。

实测跨进程场景为一个持有 BEGIN IMMEDIATE/未提交记录的 writer、三个同时 reader 可读已提交数据且看不到该记录，以及第四进程 writer 实际发生 .2 秒锁超时；terminate 持锁进程后重开无未提交记录，并可继续写入。该场景不是整机断电、硬件故障或任意并发规模证明。快照恢复使用调用方持有的预期摘要/尺寸，先验证 bytes，再将验证后的同一 bytes 写入私有临时文件供 SQLite 解析；只创建新目标，拒绝覆盖既有目标。快照身份不构成任意外来数据库准入。

资源边界：快照已在分配前 stat 检查，并用预算+1 有界读取防止文件增长；`np.asarray`/`json.dumps` 的尺寸判断属于接受上限，不能保证任意调用者输入的分配前保护。查询 fetchall 最多10000条×4096维，内存可达数百MiB，不能宣称小常数内存或任意恶意输入资源安全；未来对外 API/完整 adapter 需前置形状/字节预检、流式读取及实际预算治理。本轮只处理受控本地合成输入。

[安装身份绑定](sqlite-numpy-r7-final-20261015/installation-binding.json)记录官方 cp312 Windows x64 wheel 锁摘要 `a7b1b6353e36a7e50de2973a38d705c88ee93adcf120673cee7f45a4a3fa223a`，uv frozen sync 校验下载 against lock。本轮未另行保留 wheel ZIP，独立校验的是已安装 RECORD 文件，不能冒称再次对保留 ZIP 做完整摘要核验。实际已加载 OpenBLAS DLL SHA256 `ed4f167a5330424524f45258e7ca2c8d7f03c0cba1f30ee4985553ac1f88ecf8`；构建配置为 scipy-openblas64 0.3.34.106.0。实际加载 SQLite DLL SHA256 `5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656`，与 root 派生输入匹配。完整配置/已加载 DLL 在[运行身份输出](sqlite-numpy-r7-final-20261015/runtime-identity.stdout.log)，这不是完整 native SBOM/漏洞扫描。

root 已对精确 NumPy 2.5.4 官方 PyPI 包公告执行 pip-audit，exit 0/0；本作者安装/锁核验使该版本审计可绑定到实际唯一安装依赖。其证据为 `.tmp/sqlite-numpy-native-audit-20261015/pip-audit.json` 及 root 收据；不能推导全部原生组件无漏洞。SQLite/OpenSSL/CPython/OpenBLAS 公告及未盘点边界由 root 单独归档。

未执行：有界性能观察（无用户 SLO，不影响最小 I/O 范围）、整机崩溃/网络盘/大规模/完整 adapter/生产全链验收。独立最终复审、root 复制复验已完成，见本报告最终核验段。未提交/推送/部署/迁移。当前生产全树覆盖不能沿用历史证据，本原型测试不等同项目提交门槛。
