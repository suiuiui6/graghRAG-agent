# SQLite＋NumPy安全运行库隔离验证计划（R7）

用户明确要求验证此前推荐的SQLite＋NumPy安全运行库方案。复用既有替换设计，采用writing-plans、TDD、独立评审及verification-before-completion；不修改生产、系统DLL、主锁、原数据，不提交/发布，不启动goal/Harness。

## 范围与能力边界

本轮是运行库安全准入及最小真实输入输出验证，不是完整VectorStore或Chroma where兼容编译器。标准库sqlite3承担参数绑定、事务、持久化及backup；NumPy承担有界精确cosine，应用不加载pickle或任意SQL/扩展/外来数据库。R6数值/日志证据保留，不能将新原型的有限source过滤冒称全Chroma过滤已迁移。

优先固定受支持Python3.12构建及标准库SQLite，记录官方构建artifact与SHA256、精确Python/SQLite/NumPy和实际原生依赖。SQLite至少覆盖官网当前列出的适用修补范围，当前已知最低3.53.2；版本达标只是已列公告核对，非任意漏洞不存在的证明。若标准库不达标，先报告APSW等绑定备选的能力/构建边界，独立复核局部设计后才使用，不替换旧DLL。

## 文件所有权

- runtime debugger：`.tmp/sqlite-runtime-r7-20261015/`和`docs/review/2026-10-15-sqlite-runtime-discovery.md`，官方artifact/新解释器/真实runtime只读探针及收据。
- coder：`.tmp/sqlite-numpy-r7-20261015/`、`docs/testing/sqlite-numpy-r7-20261015/`、`docs/testing/2026-10-15-sqlite-numpy-runtime.md`，独立uv venv/pyproject/uv.lock、最小原型和测试，先红后绿。
- reviewer：`.tmp/sqlite-numpy-r7-review-20261015/`及`docs/review/2026-10-15-sqlite-numpy-runtime-review.md`，先审设计接受条件再审最终依赖/测试/独立新输入。
- root：本计划/受影响总体设计/接续记忆及复制复验收据，保留其他任务改动。

## 执行与接受条件

局部runtime修订（实际probe后独立复核条件通过）：固定Astral Python3.12.15原构建实际SQLite3.53.1，不满足3.53.2floor。优先在全新派生profile中组合该官方Python与SQLite官方Windows x64 3.54.0 DLL，保留原artifact/base、旧环境和系统DLL。该组合是项目派生构建，不承袭上游整体测试/支持声明。DLL ZIP须核官方下载页SHA3-256，固定单sqlite3.dll目标；完整源/派生manifest证明源不动且派生原始文件仅该DLL不同，实际PE x64/export/import与加载路径、source_id/compile_options、连接硬化和全部真实标准库sqlite3行为必须再验。若ABI或行为失败，保留失败再评估APSW，不降低floor或悄悄替换旧环境。

1. 发现并安装官方固定Python3.12独立artifact，仅写新目录，冻结来源、digest与关键DLL身份；实际读取SQLite source_id/compile_options、defensive/trusted_schema/extension限制能力及SSL运行库，不以uv.lock锁住解释器的假象代替收据。
2. reviewer独立审本计划与runtime方案；coder用该精确解释器创建独立uv venv，NumPy精确版本优先既有2.5.4但须核cp312/Windows兼容与当日公告；无Chroma/Lance/PyArrow依赖。完整锁与安装identity相同，记录wheel/hash、NumPy构建/OpenBLAS等原生身份及可得SBOM。
3. 先写有效行为红测试，再实现固定schema的最小记录store（ID/source/text/metadata JSON/向量BLOB及维度），参数绑定值、不将外部键或条件拼SQL；SQL模板和列名固定在代码。不pickle，不自动执行schema/模型配置，扩展加载显式禁用。连接启用并实际核实defensive=true、trusted_schema=off、外键、长度/SQL等资源预算；配置失败不得默默降级。每线程/进程独立连接，WAL只对本机文件，不承诺网络盘。
4. 验证真实批写原子性/重复ID失败不部分写入、按ID读删/按source参数过滤删除/恶意特殊字符串不注入、维度及NaN/±Inf拒绝、持久化重开（新子进程）、NumPy cosine同向/正交/反向1/.5/0和filter先于top-k。原型维度/数值格式明确，不声称全生产数值等价。
5. 使用原生backup从受控数据库生成封存快照，可信预期hash/尺寸/schema/integrity核验后只恢复到新目标；篡改/截断/非DB文件必须失败且不影响原库。hash校验不能证明任意外来数据库可信，禁止接受任意外部manifest/SQL/NPY/pickle；外来DB隔离恢复治理仍非本原型准入。
6. 实测独立进程并发读/写、真实锁冲突超时/错误、事务中止回滚与重开恢复（合成数据），记录检测范围；不将线程或mock冒称跨进程崩溃恢复全验收。可做有界合成规模性能观察但没有用户SLO，不以无SLO试跑宣称满足生产规模。
7. 对精确安装锁执行当日pip-audit（不ignore）；分别核SQLite官网公告修补与Python构建支持/已知组件、NumPy/OpenBLAS原生边界，未盘点/未扫描项保留待验证。不得因只两包就宣称全部原生零漏洞。
8. 冻结最终源码/输入/依赖/命令/日志/退出码；reviewer私有复制独立新夹具真实测试，root复制复验。回流权威设计与memory，分别标已修改/已验证/未提交/未集成。当前产品有他人源码漂移，旧双90不可作为当前全树通过证据；本轮不触发生产提交。

## 出口

独立设计复核条件通过（详见同日sqlite-numpy-runtime-review）：可信快照预期hash/尺寸只由调用参数/可信内存提供，不能信任与DB同目录可同时篡改的manifest；恢复失败不得覆盖原目标。所有连接（含读/备份/恢复）都核硬化设置，不将trusted_schema=off当任意SQL沙箱。原型使用稳定缩放归一化支持极大/极小有限非零向量；零范数明确输入拒绝，仅限本原型策略、不宣称与Chroma零向量行为完全一致；任何非有限派生score报错，不以nan_to_num吞错。top-k需明确范围和确定性tie规则，不随NumPy分区算法隐式改变。

给出基于最终构建的结论：可作为隔离开发候选、部分通过或阻断，列明实际版本、修补核对、测试覆盖和未验证项。只有真实runtime、核心I/O及独立安全复核通过才可进入完整adapter计划；仍不自动授权正式生产替换、原数据迁移或忽略Chroma四公告。
