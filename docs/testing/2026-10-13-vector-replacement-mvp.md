# 向量组件替换隔离 MVP

状态：本轮隔离能力评估已完成；**原生能力 PASS，直接兼容替换 BLOCKED**。仅授权设计与合成数据评估，无产品集成、现役索引访问或数据迁移。不得把本报告当完整适配器、迁移或项目验收通过证据。

工作目录 `.tmp/vector-replacement-mvp-20261013/`；隔离 Python 3.12.8，独立 `pyproject.toml`、`uv.lock`、`.venv`。所有测试数据均为脚本生成，未读取 `.env`、现役 output、研究原文或 Gold，未调用模型服务。未改 backend/frontend 代码、测试或锁。

## 官方能力边界

- [PyPI 0.40.0](https://pypi.org/project/lancedb/0.40.0/)：Python >=3.10，提供 cp310-abi3-win_amd64 wheel，Python 3.12 classifier；默认 x86-64-haswell，要求 AVX2/FMA/F16C。pre-Haswell 需另行验证 lancedb-compat，不推定本轮支持。
- [官方 Python API](https://lancedb.github.io/lancedb/python/python/)：本地 connect/create_table/search/delete；where/delete 支持 Expr/col/lit。以字段白名单和有界语法映射过滤，不接收任意 SQL。
- 同一 API 文档：read_consistency_interval 默认 None 不检查其他进程更新；本探针显式 timedelta(0) 并用已有父 handle 检查子进程提交。
- [官方向量检索说明](https://docs.lancedb.com/search/vector-search)：量化 ANN 距离不是原始向量精确距离。本轮不创建 ANN，采用精确 cosine 扫描。消费者 score 为 round((2-distance)/2,4)。

## 命令与历史失败

相对路径以下均以隔离工作目录为 cwd；UV_CACHE_DIR 指向其 uv-cache。

| 顺序 | 命令 | 结果 |
|---|---|---|
| 1 | uv venv .venv --python 3.12（首轮 cwd 为仓库根） | exit1，interpreter cache 写权限拒绝，未创建根 venv；详见 venv-01-failure.log |
| 2 | uv venv .venv --python 3.12 | exit0，Python3.12.8，venv-02.log |
| 3 | uv sync | exit2，PyPI 网络 socket10013，sync-01.log |
| 4 | uv sync（正规 require_escalated） | exit0，43实装/44含项目锁，下载12m25s，sync-02-approved.log |
| 5 | uv lock --offline --project runtime-lock | exit0，纯运行锁18项含项目、17 registry |
| 6 | 复制纯运行pyproject/lock后 uv sync --frozen --offline | exit0，卸载26审计工具依赖，最终仅17运行包 |
| 7 | audit-tools环境 python -m pip_audit -r runtime-registry.txt --no-deps --disable-pip --format json --output runtime-audit-01.json（正规网络审批） | exit0，完整17包无已知公告，无ignore；未声称无未知漏洞 |
| 8 | .venv/Scripts/python.exe probe.py（沙箱内） | import无输出挂起，importtime定位停于asyncio；安全中断后工具进程exit1，无PASS产物 |
| 9 | .venv/Scripts/python.exe -u -X importtime -c "import lancedb; ..." | 同样停于asyncio，安全中断exit1，import-01.log保留；未证明确切内核原因 |
| 10 | .venv/Scripts/python.exe -u probe.py（正规require_escalated离线执行） | exit0，12项能力探针PASS，probe-02-approved.log / results-1791896680974061500.json |
| 11 | .venv/Scripts/python.exe sqlite_reference.py | exit0，8组参考断言通过，sqlite-01.log |
| 12 | 现有backend-quality-venv python filter_differential.py chroma（正规审批） | exit0，真实Chroma1.5.9，6合成记录18case，无backend imports/模型/遥测 |
| 13 | .venv/Scripts/python.exe filter_differential.py lance（正规审批） | exit0，Lance0.40.0，同6记录18case；5差异 |
| 14 | .venv/Scripts/python.exe freeze_evidence.py | exit0，40份文件hash收据；不复制数据库到产品目录 |

首次 pyproject 将 pip-audit 放入运行依赖，44项锁（含本地项目）为历史安装候选，已原样保留 uv-with-audit-original.lock。最终纯运行锁17 registry与实际安装17包逐项一致，缺失/版本漂移/额外项均0，详见 installed-identity.json。扫描只发送这17项包名版本。原完整后端锁及未来整合后的供应链不属于本轮通过范围。

## 验收探针

`probe.py`：小 I/O/文本/显式 float32 向量/JSON metadata 类型保真；id/source 过滤读删；$eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$and/$or；注入形状拒绝与恶意字符串作为 literal；精确 cosine 排序与原 score；原生重复 ID 行为；失败混合批次不部分提交、写后恢复；维度异常；子进程重开；跨进程已开 handle 更新可见性；全清空恢复；12 独立连接/4线程并发追加；最后 5000×512 合成写入与30次查询。先小 I/O，通过后才运行规模。

`sqlite_reference.py`：真实 sqlite3 参数绑定、metadata/float32 BLOB 保真、唯一键、事务回滚、backup、清空恢复、子进程重开、5000×512 NumPy 精确 cosine。完整 adapter、跨进程缓存、多进程并发及强制终止恢复均未覆盖。

## 实际能力结果与局限

Lance12项全部PASS。3维手算向量的cosine distance为0/1/2、score为1/0.5/0。`read_consistency_interval=0` 下，已有父handle看到子进程提交；新进程重开也取得相同3ID。失败混合批次包含错误维度或错误整数字段，均拒绝且count不变，随后有效写删可恢复。该结果不证明强制终止/掉电/磁盘满时的原子性。

Lance原生add允许重复ID，探针明确验证2条同ID，随后删除并恢复唯一记录；该PASS是能力边界被证实，不是原VectorStore唯一ID契约已保持。完整原ID幂等/重复批处理策略未实现。

原binary64向量以binary列+`<f8` dtype往返字节完全相同，SHA256 `59bf08d7ab9c2933d220196ab581881bdf378244fc4193b9d67ef685c5286a19`；float32派生列最大绝对损失约7.2475e-9，因此float32检索结果近似一致不能证明原向量无损。未实现完整迁移工具。

12独立连接/4线程并发append后15个唯一ID可读；日志出现一次`latest_version_hint.json`写入os5权限warning。保留warning，未证明任意多进程写/强杀/版本hint异常的全部恢复边界，不能宣称并发无风险。NumPy本机CPU特征AVX2/FMA3/F16C为true；CIM读取沙箱拒绝。没有验证pre-Haswell机器或compat轮。

| 合成规模 | 写入 | 查询 |
|---|---:|---:|
| Lance 5000×512 exact scan，30次自查询top1 | 0.026997s | p50 12.153ms / p95 17.744ms |
| SQLite5000×512+NumPy参考 | 0.086200s | 已加载/归一化矩阵warm p50 0.549ms / p95 4.237ms；另读取BLOB 0.021008s |

两者计时边界不同，不能直接以该表选型。未测RSS、设计5001跨页固定版本G、30次预热+100正式采样、完整top-k NumPy差分、100K或生产SLO；随机自查询仅断言top1，规模结果只是局部能力探针。

## 真实过滤差分：5项兼容差异

[机器差分](vector-replacement-mvp-20261013/filter-differential-summary.json)及两份原始cases保留18项输入、ID输出或真实拒绝异常；13项状态/ID相同，5项不同。

| 条件 | Chroma1.5.9 | 当前Lance Expr映射 |
|---|---|---|
| source `$ne: s1` | b,c,d,f，包含缺字段b | c,d,f，SQL NULL排除b |
| source `$nin: [s1]` | b,c,d,f | c,d,f |
| active: 1 | 合法返回空ID | 强类型mapper拒绝 |
| page: true | 合法返回空ID | 强类型mapper拒绝 |
| missing_field `$ne: anything` | 全6条 | 字段白名单拒绝 |

这推翻“仅操作符替换即可保持完整where”的假设。应只重开过滤存在性/类型语义设计；需要显式存在位和类型语义，或经批准更改公共契约。不能接受任意用户SQL来绕过差异。本探针只演示固定字段、深度与每层长度限制，无全局AST节点预算，不是生产安全过滤器。未为掩盖差异临时补完整mapper。

## 冻结与建议

**建议保留LanceDB为待适配候选，否决直接替换就绪。** SQLite参考证明本地事务/精确检索路线可行，但完整adapter及应用屏障未实现，同样不是可直接集成候选。下一阶段须先关闭过滤差异、唯一ID/完整导出/快照/应用一致性契约，再补适配层与真实消费者测试。

永久证据位于 [manifest.json](vector-replacement-mvp-20261013/manifest.json)，40文件逐一SHA256；manifest SHA256 `2d823ba78b78574e7a95680257a498c80501f150cffb8c0841be34ae3f131d23`，probe SHA256 `9d9983bb0085cda1a4d92f535d8e74faac55b84c987df15179d0a333de355e79`，最终uv.lock SHA256 `ab27e2d7dc601aeff7b004502382ef329128115f7812b76f26e72699fe99986d`。脚本/锁/日志/原始JSON已复制；合成数据库留在独占.tmp，脚本可重现，不包含产品数据。

未运行：完整VectorStore适配器、全链消费者/应用屏障、Chroma重复ID差分、固定G分页、强制终止恢复、多进程并发写、生产数据只读盘点/迁移、主项目依赖整合扫描、全部后端测试与双90。未commit/push/deploy，未关闭原Chroma安全公告。根负责人负责将受影响过滤结论回流设计及memory；独立评审另附，不以本报告替代。
