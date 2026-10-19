# 向量替换候选原生安全独立核查（2026-10-14）

## 审查总结

原生安全门槛仍待验证，不能以18项PyPI审计零公告放行。SQLite观察针对设计中的SQLite+NumPy基线及当前Python运行库；本轮没有证明LanceDB存储路径加载或调用SQLite，不把环境存在SQLite当成Lance路径已受影响。已取得实际运行库指纹、57个wheel原生文件摘要及两份随轮子发布的SBOM；尚未执行完整RustSec/C++/BLAS及CPython补丁可达性审计。问题统计：High 2项、Medium 1项；未认定实际可利用漏洞。

范围：只读 `.tmp/vector-errors-testenv-20261014/.venv`；合成SQLite仅内存连接。不读取原业务库/.env/provider，不修改环境、DLL、生产代码或旧冻结材料。其他任务修改保留。报告不是生产放行或完整供应链证明。

## 实际证据

执行命令：`.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/vector-native-audit-20261014/probe.py`，2026-10-14，exit0。SBOM提取 `.../sbom.py` exit0。详见本地 `.tmp/vector-native-audit-20261014/runtime-native.json`、`sbom-summary.json`、两个原始SBOM；均未进入旧冻结。

|组件|实际观察|证明边界|
|---|---|---|
|CPython|3.12.8，MSC1942 x64|解释器版本已知；补丁/构建来源及全部stdlib公告未审计|
|SQLite|3.45.3，threadsafety3，ENABLE_FTS3/4/5，THREADSAFE1|新内存连接defensive=false、trusted_schema=1；仅该探针连接setconfig后true，不代表产品/候选所有连接已加固|
|LanceDB|0.40.0，cp310-abi3-win_amd64，`_lancedb.pyd` SHA256 `c0472c885b0df1a0f10b91aa52d33b792b1e684d28b37581f995ea3e68533756`|wheel内附800组件CycloneDX，metadata标all_targets=true，因此不是实际Windows可达代码清单|
|Lance/Arrow Rust|SBOM中Lance13.0.0、Arrow58.4.0、DataFusion54.1.0、object_store0.13.2和0.14.1|版本盘点可用；未完成每个RustSec范围匹配/feature及调用可达性核查|
|PyArrow/C++|Python26.0.0；cpp_build_info26.0.0，git `446167169a0dc547e00e1bc29f417a40c0ca267a`，description apache-arrow-26.0.0-rc0；34个native文件|未发现随轮子SBOM；rc0描述是实际构建元数据，不据此自行判定为有漏洞版本|
|NumPy/BLAS|NumPy2.5.4；21个native文件；构建元数据scipy-openblas0.3.34.106.0，USE64BITINT，Haswell|BLAS实际映射/全部C库版本未完整独立核验；未发现随轮子SBOM|
|pydantic-core|2.50.1，1个native文件；99组件SBOM|未完成99组件公告扫描|

LanceDB SBOM SHA256 `96f7bac683f2f951dd46f05e5081da8f66deae65d3cb7bee8ff4fc264c9190e2`。锁收据18包及PyPI审计0来自已冻结测试环境收据，不是本轮重新跑pip-audit；原生盘点为本轮新执行。系统有cargo/rustc，但无cargo-audit；本轮未安装工具。

一次补充展示命令因读取SBOM未显式UTF-8导致UnicodeDecodeError exit1；随后同一只读解析以encoding=utf8执行exit0。未吞掉失败，原始SBOM没有被改写。

## 问题清单

### 🟠 High：SQLite补丁与恢复入口门槛开放

位置：`docs/design/2026-10-13-vector-replacement-design.md:55-57`，以及本次runtime-native.json（运行观测，不是生产代码缺陷结论）。

[SQLite官方CVE表](https://www.sqlite.org/cves.html)列：2025-3277/29087修复3.49.1（concat_ws大分隔输入）、2025-6965修复3.50.2（任意SQL）、2025-7709修复3.50.3（坏FTS5数据库）、2026-11822/11824修复3.53.2（任意SQL+FTS5+defensive关闭）。当前3.45.3未包含这些修复，且探针观察到FTS5与初始defensive=false；缺少任意SQL/恶意库可达性证明，不能直接推断可利用，也不能标免疫。绑定SQL参数不证明恢复导入的文件可信。

最小解决路径：新建独立Python3.12精确补丁构建环境，核构建来源/hash、实际sqlite_version/source_id/编译选项，优先要求包含上述适用修复（本次官方表最高3.53.2）；重跑锁环境及数值/完整适配合同。不要替换系统DLL。若暂用旧运行库，须逐项证明SQL来源、DB来源/恢复完整信任链和连接配置，并独立审查风险决策；这属于适用性处理，不能写成漏洞代码已修。

加固示例（未实施；必须配合连接生命周期和功能复验）：

```python
# before: default connection settings observed by probe
connection = sqlite3.connect(path)
# after: proposed connection factory; fail if capability absent
connection = sqlite3.connect(path)
connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
connection.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)
assert connection.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE)
```

此示例不是修补所有SQLite公告；还需不暴露SQL/扩展加载、受控schema、资源限额/超时、可信封存快照及隔离恢复检查。[SQLite官方安全建议](https://www.sqlite.org/security.html)支持这些措施，read-only不等于恶意数据库安全。

### 🟠 High：CPython与wheel原生供应链尚未完整审计

位置：上述设计55-57及锁环境`pyproject.toml:5-6`（锁定Python minor不能锁解释器补丁及SQLite）。

[Python3.12.8发布页](https://www.python.org/downloads/release/python-3128/)已标superseded；[3.12.15官方说明](https://www.python.org/downloads/release/python-31215/)为security-only/source-only，3.12.10为最后提供常规Windows安装器版本。不能承诺直接安装官方3.12.15Windows exe，也不能只升级pip依赖假装修补stdlib。其SSL/tarfile/zipfile等修复须按项目调用评估；本轮未将任何公告判可利用。

建议before/after：`requires-python ==3.12.*` + 隐含旧系统runtime → 保留minor约束，同时登记精确受支持构建来源、artifact hash、运行SQLite及原生SBOM，独立环境验收后才修改主锁/部署。LanceDB800组件及pydantic-core99组件SBOM可作为输入，不宜再声称Rust依赖不可盘点。下一轮以隔离锁定扫描工具对SBOM中的Cargo purl进行官方RustSec匹配，冻结数据库版本/时间，核Windows feature；对缺失SBOM的Arrow/OpenBLAS取得官方构建清单或受控构建收据。未执行前保持待验证。

### 🟡 Medium：Arrow输入验证/资源界限需进入恢复契约

位置：设计第7节（142-148），尚无完整恢复实现可验。

[Apache公告](https://security.apache.org/projects/arrow/)列CVE-2026-25087影响C++15.0.0..23.0.0、23.0.1已修；实际C++26.0.0不在该列范围。2023-47248影响PyArrow<=14.0.0，实际26.0.0在修复之后；2024-52338为R绑定专属，本轮无R。2024-41178 object_store<=0.10.1日志泄露，而SBOM列0.13.2/0.14.1在修复之后。这些是指定公告的有界核对，不是整个Arrow/Rust供应链零漏洞结论。

[官方安全模型](https://arrow.apache.org/docs/dev/format/Security.html)要求验证不可信Arrow数组；IPC还有压缩资源风险，C Data接口不可接受不可信指针生产者。建议before/after：未经可信校验直接恢复目录/批次 → 先验证封存来源/manifest/hash及大小预算，在隔离进程读取后validate(full=True)并检查schema/数量/向量边界，合格才交付门面。validate本身不能代替安全补丁或读取前资源隔离；恢复未实现/未测试，不能标完成。

## 优先级与交接

1. P0：保持生产替换阻断；继续隔离兼容修复，勿改旧冻结。
2. P0：独立精确Python3.12补丁构建及SQLite修复版选择验证；连接工厂安全设置和只读恢复信任链审查。
3. P0：使用已取得800/99组件SBOM完成固定数据库版本的RustSec扫描、Windowsfeature归属及发现处理；Arrow/OpenBLAS补充构建清单。已有官网Lance安全页无公告不能替代扫描。
4. P1：恢复前格式/schema/full validation及资源限制的正常/异常行为测试。

原生门槛状态：**待验证/BLOCKED**。这次完成的是盘点及逐项有界判断，没有更新任何产品依赖或修复Chroma四公告，没有提交/推送/部署。memory由主负责人合并接续。

## 归档文件清单

本轮新增源/收据均在 `.tmp/vector-native-audit-20261014/`：`probe.py`、`runtime-native.json`、`sbom.py`、`lancedb-sbom.json`、`pydantic-core-sbom.json`、`sbom-summary.json`、`manifest.json`。`manifest.json`记录前六项SHA256、实际/冻结锁hash及命令退出码；主负责人可整体复制到新的 `docs/testing/vector-native-security-20261014/`，不覆盖旧冻结。报告路径 `docs/review/2026-10-14-vector-native-security-review.md`。完整RustSec未执行，本turn不安装/编译cargo-audit。

## 2026-10-15 续审：固定RustSec及实际PE扫描

本节新增High阻断，原上方“RustSec未执行”仅为2026-10-14历史状态。**候选LanceDB0.40.0不能安全放行**：固定数据库版本范围扫描实际产生20记录/18唯一漏洞公告及5警告；不能把它们全认定为Windows可利用，但也不能宣称只换掉Chroma即可安全清零。pydantic-core99组件在同一RustSec快照中零匹配，仅限该清单和该数据库。当前统计High3/Medium1，不将版本match直接提升为已证实可利用Critical。

工具官方[rustsec/rustsec cargo-audit/v0.22.2](https://github.com/rustsec/rustsec/releases/tag/cargo-audit/v0.22.2)，asset439294720，zip SHA256 `0a7316540862c13d954f648917ceacca593747baed6eec180fafa590be2710ab`与官方API digest完全一致；exe SHA256 `0157f5ce1ce9fd4fb0a1f7c79af1229771d1f80b6c2613ddb0d9200a8ba73946`，真实--version0.22.2。仅解压到独占tooling，未全局安装/构建，CARGO_HOME/TARGET_DIR均指向tooling。

数据库[官方RustSec](https://github.com/RustSec/advisory-db)固定commit `edb58f5974b83eb8302332821cb6d389777aa351`，commit时间2026-10-14T22:18:32+02:00，tar SHA256 `0c3e3b16dc0bdf62a446b2b7808a567bfcaab9f52fad6336899c1306eecbef2c`。工具加载1329条公告。工具JSON的last-commit/last-updated为null，故不伪称工具自行报告commit；外部git rev-parse、干净工作区与完整archivehash绑定实际快照。

`make_inventory.py`逐项验证SBOM名称/版本/PURL/hash唯一性，生成明确SYNTHETIC标头的版本清单：LanceDB800（799crates.io+1本地path component）、pydantic-core99（均crates.io）。没有依赖图/feature解析，不能称真实Cargo.lock或生产resolver锁。`run_scan.py`真实命令及退出码见scan-receipt；使用--db固定路径、--no-fetch、--json、--deny warnings，无ignore/target/severity过滤。--no-yanked仅使动态registry撤回状态查询NOT_RUN，不能把本次称完整yanked扫描。

|输入|exit|匹配|范围|
|---|---|---|---|
|LanceDB SBOM inventory800|1|20漏洞记录/18唯一ID；2unmaintained+3unsound|all_targets潜在组件，非Windows可达清单|
|pydantic-core inventory99|0|0漏洞、0警告|该固定清单/DB；不含所有C原生依赖|
|真实_lancedb.pyd静态bin扫描|1|9漏洞记录+1unmaintained+3unsound|工具明确未cargo-auditable，只从panic痕迹恢复309依赖，不完整|

PE只读检查没有`.dep-v0`section，terminal日志明确`not built with cargo auditable...incomplete (309 dependencies recovered)`。这为具体版本出现在实际wheel提供补充证据，不能证明漏洞函数可触发，也不能将未恢复的组件标为不适用。读取上限256MiB（实际235759104bytes），未执行二进制代码，未构造漏洞payload。

### 🟠 High：实际发布wheel包含尚未处理的RustSec版本匹配

位置：独立环境`lancedb/_lancedb.pyd`（hash如上方表）、官方v0.40.0`python/Cargo.toml:34-44`和`Cargo.lock`，属于候选供应链阻断，不是生产新引入缺陷。

|crate及版本|匹配公告|官方patched范围|实际PE恢复命中|
|---|---|---|---|
|h2 0.3.27|[RUSTSEC-2026-0258](https://rustsec.org/advisories/RUSTSEC-2026-0258.html)|>=0.4.16|未恢复，不代表不包含|
|pyo3 0.28.3|[RUSTSEC-2026-0176](https://rustsec.org/advisories/RUSTSEC-2026-0176.html)|>=0.29.0|是（仍未证函数可达）|
|pyo3 0.28.3|[RUSTSEC-2026-0177](https://rustsec.org/advisories/RUSTSEC-2026-0177.html)|>=0.29.0|是（仍未证函数可达）|
|quick-xml 0.40.1|[RUSTSEC-2026-0194](https://rustsec.org/advisories/RUSTSEC-2026-0194.html)|>=0.41.0|是（仍未证函数可达）|
|quick-xml 0.40.1|[RUSTSEC-2026-0195](https://rustsec.org/advisories/RUSTSEC-2026-0195.html)|>=0.41.0|是（仍未证函数可达）|
|quinn-proto 0.11.14|[RUSTSEC-2026-0185](https://rustsec.org/advisories/RUSTSEC-2026-0185.html)|>=0.11.15|未恢复，不代表不包含|
|quinn-proto 0.11.14|[RUSTSEC-2026-0338](https://rustsec.org/advisories/RUSTSEC-2026-0338.html)|>=0.11.18|未恢复，不代表不包含|
|quinn-proto 0.11.14|[RUSTSEC-2026-0339](https://rustsec.org/advisories/RUSTSEC-2026-0339.html)|>=0.11.17|未恢复，不代表不包含|
|quinn-proto 0.11.14|[RUSTSEC-2026-0340](https://rustsec.org/advisories/RUSTSEC-2026-0340.html)|>=0.11.18|未恢复，不代表不包含|
|quinn-proto 0.11.14|[RUSTSEC-2026-0342](https://rustsec.org/advisories/RUSTSEC-2026-0342.html)|>=0.11.17|未恢复，不代表不包含|
|rsa 0.9.10|[RUSTSEC-2023-0071](https://rustsec.org/advisories/RUSTSEC-2023-0071.html)|无已列patched版本|是（仍未证函数可达）|
|rustls 0.21.12|[RUSTSEC-2026-0346](https://rustsec.org/advisories/RUSTSEC-2026-0346.html)|>=0.23.46|未恢复，不代表不包含|
|rustls 0.21.12|[RUSTSEC-2026-0349](https://rustsec.org/advisories/RUSTSEC-2026-0349.html)|>=0.23.46|未恢复，不代表不包含|
|rustls 0.23.45|[RUSTSEC-2026-0346](https://rustsec.org/advisories/RUSTSEC-2026-0346.html)|>=0.23.46|是（仍未证函数可达）|
|rustls 0.23.45|[RUSTSEC-2026-0347](https://rustsec.org/advisories/RUSTSEC-2026-0347.html)|>=0.23.46|是（仍未证函数可达）|
|rustls 0.23.45|[RUSTSEC-2026-0348](https://rustsec.org/advisories/RUSTSEC-2026-0348.html)|>=0.23.46|是（仍未证函数可达）|
|rustls 0.23.45|[RUSTSEC-2026-0349](https://rustsec.org/advisories/RUSTSEC-2026-0349.html)|>=0.23.46|是（仍未证函数可达）|
|rustls-webpki 0.101.7|[RUSTSEC-2026-0098](https://rustsec.org/advisories/RUSTSEC-2026-0098.html)|>=0.103.12, <0.104.0-alpha.1; >=0.104.0-alpha.6|未恢复，不代表不包含|
|rustls-webpki 0.101.7|[RUSTSEC-2026-0099](https://rustsec.org/advisories/RUSTSEC-2026-0099.html)|>=0.103.12, <0.104.0-alpha.1; >=0.104.0-alpha.6|未恢复，不代表不包含|
|rustls-webpki 0.101.7|[RUSTSEC-2026-0104](https://rustsec.org/advisories/RUSTSEC-2026-0104.html)|>=0.103.13, <0.104.0-alpha.1; >=0.104.0-alpha.7|未恢复，不代表不包含|
|paste 1.0.15|[RUSTSEC-2024-0436](https://rustsec.org/advisories/RUSTSEC-2024-0436.html)|无已列patched版本|未恢复，不代表不包含|
|unsafe-libyaml 0.2.11|[RUSTSEC-2024-0449](https://rustsec.org/advisories/RUSTSEC-2024-0449.html)|无已列patched版本|是（仍未证函数可达）|
|event-listener 5.4.1|[RUSTSEC-2026-0221](https://rustsec.org/advisories/RUSTSEC-2026-0221.html)|>=5.4.2|是（仍未证函数可达）|
|lru 0.16.4|[RUSTSEC-2026-0253](https://rustsec.org/advisories/RUSTSEC-2026-0253.html)|>=0.18.2|是（仍未证函数可达）|
|memmap2 0.9.10|[RUSTSEC-2026-0186](https://rustsec.org/advisories/RUSTSEC-2026-0186.html)|>=0.9.11|是（仍未证函数可达）|

PyO3两条涉及List/Tuple iterator nth/nth_back及PyCFunction::new_closure线程安全，修补>=0.29.0。官方v0.40.0Python cdylib直接依赖PyO3 0.28，features abi3-py310/chrono/uuid，实际PE恢复0.28.3；因此不能按“未启用云功能”排除。仍须核固定源码中这些函数的调用、输入范围及detach/跨线程路径；GIL存在不是0177的充分排除条件。

memmap2涉及越界offset/len的advise/flush指针算术（公告包括Windows equivalent），lru涉及panic Drop/catch_unwind后的cache pop/eviction，event-listener涉及非Send tag跨线程；不能仅以本地嵌入式运行排除。TLS/HTTP/QUIC/XML/RSA项需按实际wheel features、连接配置、调用日志及恢复入口逐项判定，而不是版本比较直接判可利用。

有界查新：[GitHub latest](https://github.com/lancedb/lancedb/releases/latest)及[PyPI JSON](https://pypi.org/pypi/lancedb/json)本次均0.40.0；上游main锁（最近改动commit8bb04d0fee9a3a42071b25c312f5453dadb93745）仍PyO3 0.28.3/rustls0.23.45。未观察到可直接升级且修复这两者的新发行版。v0.40.0python/Cargo.toml default features含remote和多个cloud backend，但源码defaults不是精确wheel构建attestation。未升级/重建产品。

最小下一步：①保留R6兼容证据，重开候选安全局部设计；②优先逐项固定函数/feature可达性独立核查（尤其PyO3/内存安全）；③若继续Lance，采用经审核的新上游发布或独立锁源码补丁构建，至少处理已匹配修补范围及无patch RSA的功能移除/可达性决策，取得actual build SBOM、重跑隔离真实行为/安全/消费者矩阵；④对SQLite+NumPy替代基线同时推进受支持Python/SQLite精确构建审计。不能直接更新一个Python lancedb包或禁云配置就认为wheel内Rust依赖已修。

下载官网直链初次连接超时并在90秒有界重试后exit28（只残留部分文件，从未执行）；唯一官方资产API重试exit0且官方digest校验通过。没有隐藏下载失败，没有退回自行编译或无限尝试。

本次新增证据仅`.tmp/vector-native-audit-20261014/tooling/`，主要机器入口：`scan-summary.json`、`scan-receipt.json`、`binary-scan-receipt.json`、`inventory-receipt.json`、`tool-receipt.json`、`db-receipt.json`、`release-check-receipt.json`；原始`lancedb.audit.json/.exit/.log`、`pydantic-core.audit.json/.exit/.log`、`lancedb.binary.audit.json/.exit/.log/.terminal.log`；`matched-advisories/`、`rustsec-db.tar`、两个`.inventory.lock`及执行脚本。由root归档到20261015新目录；旧7项freeze未修改。
