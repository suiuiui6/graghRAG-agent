# R8 SQLite 与真实 Chroma 独立差分（2026-10-17）

状态：OPEN，已发现四位 formatter 的具体反例。未证明全域兼容。

最终更新：初轮19条四位 score 反例已在新私有快照关闭；真实Chroma全量查询缺ID现象仍OPEN，原因未定位。有限score证明不能代替全域兼容。

永久初轮证据入口：`docs/testing/sqlite-r8-oracle-20261017/`，29文件逐字复制，manifest SHA256 `27761a9b29c5c2b6cae437a880fa34c5b9c05ea9bc7e189a68a37c93d0e9d356`（root归档）。后续轮次新建目录，不改此归档。

## 输入及环境

- 来源 `.tmp/sqlite-vector-r8-20261016/backend` 独立复制至 `.tmp/sqlite-r8-oracle-20261016/diff-20261017/candidate`；原有冻结 oracle 未修改。
- `vector_store.py` SHA256 `cd03a324a407cb5f91c6516c6c9e0faeccabc47f650df06e667aaa5280c7a0f3`；四个执行输入 before/after 哈希一致，详见 comparison.json。
- 真实 Chroma 使用 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`；SQLite 使用 R7 `.tmp/sqlite-numpy-r7-20261015/.venv/Scripts/python.exe`。两个子进程完全分环境，固定合成输入，无 provider、模型或现有数据。
- 实际命令 `.tmp/sqlite-numpy-r7-20261015/.venv/Scripts/python.exe -B .tmp/sqlite-r8-oracle-20261016/diff-20261017/run.py`；编排退出0，两个子进程退出均0，日志和结果在同目录。

## 有限差分结论

135 组结果比较，134 组一致，1组存在反例。110组 where 覆盖 eq/ne/gt/gte/lt/lte/in/nin、组合条件、missing、bool、字符串、宽整数、极大/小有限浮点；接受时 IDs 集合精确比较，错误仅比成功/失败，不验证错误文本。

随机 seed `2026101701`，维度3/17/128各120记录、8查询：24组全部返回 ID→四位 score 映射精确一致，无容差。此轮未比较并列排序或 HNSW ANN recall，不能据此声称排序全域等价。

201条边界向量 `[v,sqrt(1-v*v)]`，其中 `v=.1235+(i-100)*1e-10`，查询 `[1,0]`，top_k 覆盖全部。ID182至200共19条：真实 Chroma `0.5618`，SQLite `0.5617`。原始完整结果在 chroma.json、sqlite.json、comparison.json。

## 根因验证与最小修复方向

首次可定位偏离为 candidate `vector_store.py` search 中归一化 `v/norm` 与 `q/qnorm`（复制快照约349/351行）。独立临时 probe.py 对同样201向量模拟 f32 归一化：逐元素除法模型19条不匹配；先算 f32 reciprocal 再乘模型0条不匹配。实际命令 R7 Python `-B .../probe.py`，退出0；probe.json保留完整结果。

这证明有限反例由该舍入路径解释；尚未核实上游 HNSW 源码，不能将模型吻合写成上游源码事实。建议 coder 用真实边界回归锁定结果，在双侧归一化采用单次 f32 reciprocal 再乘；新快照必须重新执行差分，不能将旧134通过沿用为最终证据。

## 未验证项与规范

完整 CRUD、错误契约、formatter 返回结构、并列排名、ANN recall、所有数值/维度输入仍需其他证据；本报告仅支持上述有限行为结论。应在 SQLite adapter 契约中记录 f32 运算顺序及四位 score 精确一致的验收要求，保留201条边界回归。当前 OPEN 已通知 root，由 coder修复后新copy复验；本代理未修改产品或候选源。

## 修后独立复验（同日 R2/R3/R4）

新copy `vector_store.py` SHA256 `da5dddc29570f7d8626565ca0c67f5cace05d67286161dd2c9bef07cb11b0636`，before/after四输入不变。目录 `.tmp/sqlite-r8-oracle-20261016/diff-r2-20261017/`：135组子进程均0；110 where、24随机ordered IDs及四位score全部精确一致。boundary共同返回ID的score全部一致，原19舍入反例关闭；但Chroma只返回193/201，SQLite201，故整组仍差异，保留原始JSON。

R3尝试原生 `query(ids=[id])` 逐ID检索，146组Chroma空结果，不能作为完整score对照；证据原样保留。R4改用每条边界独立真实单记录collection，201边界均可返回：合计335组（110where+24随机ordered+201边界）差异0、双子进程0，无容差。R2/R3/R4分别新目录，不覆盖前轮。

R4 `public.py` 用真实候选add_chunks/get_by_ids执行2例 metadata None 与含Unicode/引号/None的JSON列表往返，和默认public metadata helper的期望精确一致；退出0，public.json记录输入期望及实际值。该项是候选真实I/O+默认helper基准，未执行完整旧public VectorStore消费路径，不能冒称双实现公共契约全验证。

R4 `missing_probe.py` 真实Chroma重开R2 collection，count=201、get返回201，三次n_results201查询均返回151（缺50），单ID9现可返回。证明缺失结果并非记录未写入；首次193与重开151不同。实际退出0、missing-probe.json保留完整get/query IDs。未定位索引可见性、召回或引擎路径根因；此项明确OPEN，不能将其直接定性为HNSW ANN缺陷，更不能用R4夹具掩盖。

R4实际命令：R7 Python `-B .../diff-r4-20261017/run.py`、`-B .../public.py`；quality Python `-B .../missing_probe.py`，均0。新source与coder冻结清单的最终一致性须由root归档时核验。

## 缺ID定位：重复向量索引路径退化有强实证

新增独立输入 `.tmp/sqlite-r8-oracle-20261016/missing-rootcause-20261017/`。quality Python执行 `-B .../probe.py`、`-B .../probe.py reopen`、`-B .../batch.py`，均退出0。初轮证据未改。

真实Chroma1.5.9的六个collection各201条，实际configuration均记录 `max_neighbors=16`，ef_search分别100/1000；安装Python configuration默认ef_search100、sync_threshold1000。此Python配置仅为配置来源，不能替代Rust执行路径证明。

| 数据 | unique f32向量 | ef100首次query201 | ef1000首次query201 | ef100重开 | ef1000重开 |
|---|---:|---:|---:|---:|---:|
| near边界 | 4 | 66 | 191 | 201 | 55 |
| same完全重复 | 1 | 196 | 185 | 201 | 197 |
| distinct圆周 | 201 | 201 | 201 | 201 | 201 |

所有count/get均201。same输入与get按ID排序后f32 embeddings字节SHA完全一致，排除数据未写全或转换丢失；near/distinct输入hash与get不等，可能涉及cosine归一化，本轮不据此声称逐字写入一致。input_hash/stored_hash实际值均在initial.json，get结果hash亦保留重开记录。

所有六组n_results20均20；n_results201与250的缺失计数相同。无过滤、allids以及实际存入的where group=1等价过滤计数相同，排除仅某一过滤夹具问题。单ids路径单列，不与无过滤混用；near-100首次仅ID9过滤仍空，重开可返回。提高ef_search1000没有可靠消除不足；distinct201可完整返回，排除max_neighbors16作为固定返回容量上限。

独立新增四collection尝试batch_size100/1000：重复分别156/166、near分别70/137，连续3查询相同；返回configuration未暴露batch_size，无法证明该选项实际改变Rust缓冲区，故不采用它解释因果，更不声称已隔离brute-force路径。

**定位结论**：不足结果发生在真实Chroma向量查询/索引层；重复/近重复输入触发、区分度高的输入不触发、重开改变同数据结果，强烈支持重复向量索引路径退化。具体Rust图连接/搜索停止/持久化内部机制尚未源码或断点证实，不能写作已确认内部根因。与候选formatter舍入问题分别记录。

**契约取舍**：保留用户已确认的SQLite精确扫描，返回所有匹配记录中完整的min(k,N)，无需拟合Chroma跨重启不稳定的缺失集合。这属于明确检索算法差异，不能声称任意输入的IDs输出完全相同。四位score与非并列精确排序仍严格比较，缺ID原始结果作为近似索引适应性现象保留；单记录边界仅证明数值映射，不能关闭原查询差异。

## 最终 schema 修复快照绑定复验

从 `docs/testing/sqlite-vector-r8-r2-20261017/backend` 新复制至 `.tmp/sqlite-r8-oracle-20261016/diff-final-20261017/candidate`，冻结来源manifest SHA256 `9d4e97242ea1e536669502ab28d16a9b5beaa0dff6ce410d1726666293761cc7`；实际执行 vector_store.py SHA256 `ff84400e52da5a00f03110f2cf2faeeed222f77b89a2dd9e4bb746afda414f46`。

实际R7 Python `-B .../diff-final-20261017/run.py` 退出0，真实Chroma与SQLite两个子进程均0，335组差异0；before/after四输入hash相等。随后R7 Python `-B .../public.py` 退出0，2例真实metadata往返通过。原轮次目录均未改，新证据manifest SHA256 `02062f6c8c0c0993a26d9db366c0588746607007aef7a40af4cc6aa7549abede`。最终复验继承上述有限证明及已声明算法差异，不扩大成全域兼容结论。
