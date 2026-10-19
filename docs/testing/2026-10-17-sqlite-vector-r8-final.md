# SQLite向量适配器R8最终验证汇总

状态：隔离候选及三个消费者的实现、真实组合验证、独立schema修复复验均完成。生产源码及数据未替换，本轮未提交/推送/部署/迁移。用户已选择保留合法数据规模，旧候选的新容量上限未被带入。

最终独立证据已永久归档：[150文件清单](sqlite-r8-final-independent-20261017/manifest.json)，SHA256 `c545dbb23094257326970200bad54b2a996334059be983f32752e89206ffc2a7`。消费者32项通过；适配器18项＋独立11项＝29项及3子测试通过，exit0，schema缺口关闭，见[核心复审](../review/2026-10-17-sqlite-adapter-core-review.md)。最终schema源码再次运行335组真实双环境差分及2例public往返全部通过，两个子进程exit0、执行输入无漂移；旧反例、WAL测试夹具纠正及重跑均保留。初轮oracle另有[29文件归档](sqlite-r8-oracle-20261017/archive-manifest.json)。

## 修改与证据

- 消费者R2：[66文件冻结](sqlite-r8-consumers-r2-20261017/manifest.json)，SHA256 `63d4084f6ad92d6df1e80c3132e1ff9ac9ff385f9d392df20eb64d4ae8206f8d`。三个实际入口共享同快照页面协议、主动close，BM25单遍token化；旧Chroma仍单get回退，候选路径不走全集get。修复独立发现的首次next异常/空未close及无读取能力对象None回退。独立原29＋新3=32通过，见[消费者复审](../review/2026-10-17-sqlite-consumers-r2-review.md)。
- 适配器R2：[42文件冻结](sqlite-vector-r8-r2-20261017/manifest.json)，SHA256 `9d4e97242ea1e536669502ab28d16a9b5beaa0dff6ce410d1726666293761cc7`；vector_store源码SHA256 `ff84400e52da5a00f03110f2cf2faeeed222f77b89a2dd9e4bb746afda414f46`。写入前流式校验/磁盘暂存，64KiB载荷片段、JSON字符串窗口；分维float32评分、top-k堆、同事务读取命中载荷；恢复及重开精确schema/FK检查。每轮真实红与修复绿均保留，旧37档不改。
- root：[最终93文件证据](sqlite-r8-final-root-20261017/manifest.json)，SHA256 `b0575853e74f1dba9ead346e41d1ef347a1c84e847b2433ac382c34a3400eef9`。完整测试命令与源码前后摘要见[实际收据](sqlite-r8-final-root-20261017/combined/receipt.json)；新副本中消费者29＋适配器18＋真实组合3＝50项、3子测试全部通过，exit0，16.71秒，源码无漂移。首次组合缺私有PYTHONPATH收集失败、补正后的旧组合45通过均另存，未回写失败。

三个真实组合测试使用候选SQLite、真实Chunk及BM25，逐入口137条全部进入索引，并禁止candidate调用全集get。测试不是简化消费者替身；没有执行供应商/完整API/worker全链。共享索引的最终模型/Chunk/TableIndex仍O(N)，全量get/输出O(返回量)、堆O(k)，单逻辑记录物化是明确边界，不承诺严格RSS上限。

## 数值与合同

[真实差分与根因](../review/2026-10-17-sqlite-contract-differential.md)登记110过滤条件、24随机排序/score和201单记录舍入边界共335组，修复float32除法与倒数乘法舍入差异，另有public metadata往返。最终schema代码修订后已再次绑定相同测试；以报告最终输入摘要为准，不将旧输入当新快照。

真实Chroma的201重复/近重复记录已完整存入，但多记录查询会缺ID且重启后缺集变化；提高ef未可靠修复，高区分向量全部返回。保留全部反例，内部索引机制尚未完全定位。候选遵循已确认的精确扫描，返回完整min(k,N)，不拟合不稳定缺失集合；不能声称与Chroma ANN全域逐ID相同。metadata formatter全binary64域的形式证明未执行，有限差分不能代替证明。

## 环境与安全边界

独立锁环境实际Python3.12.15/SQLite3.54.0/NumPy2.5.4，未安装Chroma；[锁](sqlite-r8-final-root-20261017/environment/uv.lock)及完整安装命令归档。补齐固定pytest-timeout2.4.0后完成最终组合，没有屏蔽超时配置。导出全部锁依赖审计75包、已知包公告0、exit0，见[原始audit](sqlite-r8-final-root-20261017/environment/audit.json)。这不是CPython/OpenBLAS/CRT等原生组件全审。

仍未执行：生产消费者切换及现有数据迁移、全backend及其他适用子项目全量双90、供应商及完整API/worker链、性能SLO/严格OS资源上限、全原生SBOM与安全审计。现役Chroma四项公告仍在，本隔离成果没有消除生产依赖。后续集成须复验实际消费者及全部提交门槛，不能用这些专项替代。
