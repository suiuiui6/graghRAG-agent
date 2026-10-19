# R8 SQLite候选接续验证

最新R2：独立评审发现可信hash匹配但payload schema错误仍可恢复；已有效红→修复→全18项green（`schema-green.log`，exit0）。restore与已有文件构造都精确核对sqlite_schema的type/name/tbl_name/sql全集，包含三表字段、PK/UNIQUE/FK约束、自动索引、sqlite_sequence，附加trigger/view/index拒绝，同时检查foreign_key_check；重开检查先于写操作。新[42文件冻结](sqlite-vector-r8-r2-20261017/manifest.json) manifest SHA256 `9d4e97242ea1e536669502ab28d16a9b5beaa0dff6ce410d1726666293761cc7`，source `ff84400e52da5a00f03110f2cf2faeeed222f77b89a2dd9e4bb746afda414f46`。下文37文件为保留的R1历史输入，未改动。root/独立R2复验另记，不用R1报告代替。

状态：隔离候选16项专项测试通过；完整项目契约、消费者组合及独立新输入验证由root另行核验。无生产替换、迁移、提交或发布。

## 输入与改动

接续输入vector_store.py SHA256 `cd03a324a407cb5f91c6516c6c9e0faeccabc47f650df06e667aaa5280c7a0f3`。最终源码SHA256 `da5dddc29570f7d8626565ca0c67f5cace05d67286161dd2c9bef07cb11b0636`。

- 外层embedding ndarray形状、documents/metadatas容器先验证，避免不可信len钩子执行并误分类为存储故障。
- public add_chunks使用内部_StreamJSON表示entity_types/section_path/entity_ids；JSON字段分窗口转义和数据库分片写入，读回仍为原JSON列表。独立调用_build_chroma_metadata默认返回历史完整字符串，其调用返回值本身的单字段物化仍需内存；实际写入口不再调用该完整编码路径。
- f32规范化改为reciprocal乘法。201条实际Chroma舍入边界中旧除法在182号失败，修复后全部通过；这不证明所有SIMD维度、向量分布或tie排序兼容。
- 保留64KiB数据库内部片段、8MiB页面目标及超目标单行例外；不增加记录数、维度、batch、top-k或结果总量的拒绝上限。

## 实际命令和证据

Python：`.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe`，root锁定派生SQLite3.54.0/NumPy2.5.4环境；设置`PYTHONDONTWRITEBYTECODE=1`。

最终命令：`python -B -X utf8 -m unittest discover -s .tmp/sqlite-vector-r8-20261016/tests -v`，退出码0，16项通过。最终日志与退出码在[新冻结目录](sqlite-vector-r8-20261017/final-20261017-v2.log)。

真实红证据：resources-red exit1（非法外层shape/len hook）；public-red exit1（public入口完整列表编码）；rounding-red exit1（201边界182号不一致）。中间resources-green exit1为新测试自身SQLite context manager不主动close，Windows删除占用，已改用closing；并非吞掉失败。最终全部复跑。

新增有效断言：JSON string编码窗口最大8192字符，public metadata大列表/单字符串不整串编码；5MiB/5MiB/9MiB/末行页面分别独立、无漏项，数据库片段不超过65536bytes；超页单行完整接受。既有测试含11001records、4097维、1001top-k、真实读快照并发增删、非法batch原子性、hash-before-parse备份恢复。

冻结37文件，manifest SHA256 `ff9d60f7e90477debc95f93781aaf8e239452069ccd328c75e704d78c321506a`。源码、测试、fixtures、锁及历史/最终日志分别归档，不包含虚拟环境、测试临时数据库、凭据或生产数据。旧历史final11项不冒充当前16项结论。

## 证据边界

专项通过不替代完整契约差分、全后端测试、双90或漏洞扫描。暂无严格进程RSS上限证明；页面接口必须物化单条逻辑document/metadata，调用方持有输入及最终输出、BM25模型、top-k堆均仍占内存。nested JSON递归/不合法对象及极端容器的公开入口行为需进一步独立新输入核验；不得概括为原生安全或完整Chroma所有API兼容。
