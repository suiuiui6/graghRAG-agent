# R8 可复用实现与锁定 Chroma 合成 oracle

2026-10-16；只写 `.tmp/sqlite-r8-oracle-20261016/` 与本文。保留当前 master 的其他任务改动。使用 using-superpowers、systematic-debugging；生产代码、冻结目录、真实数据、provider均未修改/调用。root负责规范及memory回流。

## 可复用路径

- `docs/testing/vector-r6-20261014/parser_port.py`：serde_json默认数值parser临时审计移植。SHA256 `18a85b55345caa9ce4ac7ea2e344cedc9561cdda8c1c0eb6824499b3a629753d`。
- 同目录 `generic_filter.py`：numeric_parse/ingress、bool/数字区别、缺失键negative规则、混合数值比较和in/nin首项类型机制；SHA256 `31f21998e01bb06c548727275168634d8ae39f04b17d962c7576b6c7a4fbb51a`。绑定pyarrow/lancedb表达式与静态key投影，不能直接用于SQLite；旧16/512/64预算是探针限制，不是正式产品合同。应抽取纯函数、以逐行typed metadata解释器替换表达式后重新差分。
- 同目录 `vector_errors.py`：typed错误且不继承TypeError，SHA256 `b9a23b941eb84a7b50c866716e0c9dbcff3b1248be7c9daf2f9f594dc7ed4661`；`safe_vector_logging.py`：安全链诊断，SHA256 `b3a0eee22c0b8d0a98cae8da58a1f8e06d71f17c925f3cf40d20afdcee058173`。需要重新注册实际SQLite函数code身份。
- 当前 `backend/vector_store.py` 的metadata构建/解析及结果字段/切片可移植；构造中的镜像降级不可照抄。`probe_store.py`仅静态Lance探针，不是完整生命周期适配器。
- R6冻结清单SHA256 `37a4ca29ce343e1621235b1bb8fdbee52beb120b67134fc3b32d1e6c1d1fbac5`；backend/uv.lock当前SHA256 `0b9618aede31fd0553ff10b845a2feb5a388d1e153c8e38549d769a3074dacf6`。当前安装版本亲测Python3.12.8/Chroma1.5.9；环境路径 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`。版本/锁文件不能代表安装环境全文件供应链证明。

## 实际 oracle

证据目录 `.tmp/sqlite-r8-oracle-20261016/`：`oracle.py`→`oracle.json`、`scale.py`→`scale.json`、`float_crud.py`→`float-crud.json`、`score_boundary.py`→`score-boundary.json`。对应日志及退出码为 `oracle.log/.exit`、`scale.log/.exit`、`float-crud.log/.exit`、`score-boundary.log/.exit`；总收据 `receipt.json`。每个命令完整前缀均为 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B`。

执行命令、源码和输入生成hash、版本、UTC、输出及退出码见 `.tmp/sqlite-r8-oracle-20261016/receipt.json`；四命令均exit0。输入完全固定合成字面量/范围生成，embedding_function=None，禁dotenv/HF；无联网模型。oracle内逐case错误是观察结果，脚本exit0不是所有case被接受。

| 边界 | 实测 |
|---|---|
| 零向量 | 写/查接受；零与任意向量cosine distance=1，项目score=.5 |
| 声明维度 | metadata.dimension=512仍接受首次2维写；首次实际写绑定2维，再写/查3维拒；空集合2维query返回空且不阻止随后2维add |
| 维度范围 | 实际1/4097维接受，0维add拒 |
| 规模 | 1001批接受；当前max batch 5461；分5000/5000/1000写11000行成功；topk1001真实返回1001；11001条集合成功 |
| 宽文档 | ASCII 1048577字符写回完整 |
| top-k | 0/-1拒；大于count接受且返回count |
| get顺序 | 插入z/a/m，传m/z/a仍返z/a/m；缺失ID忽略；重复ID和空ids拒 |
| 重复写 | 批内重复拒；已存在ID再次add不覆盖旧文档/metadata |
| get分页 | limit=0空；负offset拒；offset10000请求1001返余下1000 |
| where | {}拒；删除匹配metadata后count0，重加新metadata键立即过滤命中 |
| 宽metadata | 2**63写后读回float 9.223372036854776e18，JSON列表仍raw字符串 |

这些是反例及有限样本，不是所有合法规模/维度的穷尽证明。4096/1000/10000/1MiB新限额会拒绝已亲测合法Chroma输入，与用户保留合法规模路线不相容。

## 新发现：评分舍入不能按binary64参考声称兼容

`score_boundary.py`用201个二维单位向量，cos=.1235+i*1e-10，i=-100..100，显式query=[1,0]。真实Chroma距离经现役round(1-distance/2,4)与直接binary64数学余弦参考存在81条分歧，详见 `score-boundary.json`。这是可复现的4位分数反例，不能由放宽容差关闭。应移植Chroma实际float32转换/规范化/距离累加路径并在新SQLite执行中真实差分；未关闭前保留兼容阻断，不能将NumPy float64更精确等同合同一致。ANN排名并列也不能当唯一次序比较。

`float_crud.py`额外证明有限binary64输入[1e40,1]写入会在float32转换后被Chroma拒绝NaN/Infinity；同一大finite查询真实接受并产生NaN distances。用户此前明确拒NaN/Inf原查询值，不自动授权把所有有限大值视为非法；新实现需要明确处理有限输入转换后的政策及能力边界，不能声称当前决定已覆盖它。

## SQLite移植建议与文档回流

固定schema保存raw metadata与compat metadata、插入序号、实际绑定维度。metadata过滤纯解释器支持新增key立即可查；删除/重插入要验证顺序；add不可用UPSERT覆盖旧ID。继承typed错误和安全日志，分页扫描保留读事务及逐行预算，公共合法大小不人为截断；三个BM25消费者采用分页路径后单测全集对齐和尾页。零向量以distance1处理。资源分块不是全库容量限制。

R8设计应回流：明确元数据声明维度与实际绑定维度区别、zero接受、插入get顺序、重复ID语义、合法规模反例，并将81条评分舍入反例作为实施前必须关闭的已知问题。R6有限formatter证据不是任意binary64 formatter证明。本文不声明适配器实现完成、原生安全通过、全量双90通过、提交或生产迁移。
