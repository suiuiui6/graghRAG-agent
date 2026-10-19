# R6 宽整数记录与非有限查询：有界根因诊断

## 故障摘要

- 现象：R5候选拒绝超I64的Python整数metadata，真实Chroma1.5.9接受其中可转换为有限binary64的整数，并读回float。NaN查询也存在候选拒绝/native接受差异。
- 复现：`.tmp/vector-r6-debug-20261014/probe.py`，合成3维显式向量，独立临时数据库，无embedding/provider/真实数据调用。命令 `.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-r6-debug-20261014/probe.py` 经正规require_escalated执行，退出码0，日志及原始观察位于同目录 `probe.log/probe.exit/result.json`。脚本SHA256 `a4446ab538f7fc3cfe6a0221ccec6cd4d877e91829e5e15f4d6f2ff500433b28`。
- 环境：Python3.12.8、Chroma1.5.9，复用既有锁定后端质量oracle环境，未改依赖/主锁；候选生产环境未改。

## 根因分析

第一偏离在冻结R5 `docs/testing/vector-errors-r5-20261014/generic_filter.py:39` 的I64入口硬拒绝，encode中又有同样拒绝。Arrow int64列本身不能容纳宽整数，但真实Chroma并不要求它们走整数存储。

版本源码：此前保存的官方tag1.5.9 `rust/types/src/metadata.rs`（本地 `.tmp/vector-ingress-review-20261014/metadata.rs:649-658`）中 `MetadataValue::extract_bound` 依次尝试bool、i64、f64、String。I64提取失败可继续f64提取，不等同整个metadata非法。`rust/python_bindings/src/bindings.rs:435-439`的add参数是typed Metadata；本地 `.tmp/vector-ingress-debug-20261014/bindings.rs` 保存该源码。实际安装 `chromadb/api/rust.py:463-494`将metadata直接交给bindings.add。`rust/log/src/sqlite_log.rs:358`序列化metadata，`:292`再解析回放（缓存同目录sqlite_log.rs）。Cargo.lock锁PyO3为0.24.2；本机没有该版本完整crate源码，因此未声称独立审计其内部CPython转换实现。

数据流：原始Python int → PyO3先尝试i64 → 超界改尝试f64 → Rust Float JSON十进制 → serde_json默认数字解析 → SQLite REAL → Python float读回。**记录输入必须先经历int→float，不得套用where原始整数JSON parser规则。** where正u64的类型guard拒绝仍是另一条路径。

新oracle 11个记录边界：

| 原始值 | 原生结果 |
|---|---|
| -2**63、2**63-1 | 接受、int精确读回 |
| 2**63、2**64、-2**63-1 | 接受、float读回分别±2**63与2**64 |
| 2**63+1025、-2**63-1025 | 接受、float读回hex ±0x1.0000000000001p+63 |
| 10**100、10**308 | 接受、float读回 |
| 10**309、10**400 | PyO3 metadata入口TypeError拒绝，无该记录queue项 |

result.json同时保留真实embeddings_queue.metadata数字token，证明宽整数在序列化前已转float，不是直接解析原整数token。该组验证是有界观察，不能冒称任意Python整数或全binary64表示等价证明。

## 可执行最小修复建议

1. 在记录派生入口建立通用转换：bool保持bool；I64内int保持int；其余int执行float(value)，转换溢出/非有限应转应用invalid_input且保留cause。不是按具体数值、夹具或oracle查表分支。
2. 转换后的float通过既有**记录**serializer/parser路径派生兼容值；raw metadata_json继续保存原始int。不能把query numeric_parse直接作用于宽int。现有Python最短表示近似Rust serializer的全域一致性仍开放。
3. encode投影的_type和_int/_float列必须取派生类型与值，不能沿用原始int标签，否则仍会Arrow int64 overflow，且where比较会使用错误存储类型。compat readback返回派生float，raw单独保真。
4. 将R5 test_input_rejection中metadata2**63“必拒绝”旧假设在新R6副本更新成真实接受/type/bit断言；保留10**400等真实拒绝与其他有效断言，不改旧冻结。
5. 回归应覆盖I64两端、两端外相邻整数、ulp附近整数、正负宽整数、多数量级、binary64溢出；对int/float filters、$eq/$ne/大小比较、同类$in顺序、get/query及原payload独立保真做真实双端差分。禁止只验证add成功。

## NaN查询边界

本次4种query：finite返回正常0距离；NaN、+Inf、-Inf均被native接受且本次返回的3个距离全为NaN。绑定源码 `bindings.rs:691` 采用Vec<Vec<f32>>；这条路径不是where JSON数值literal。非有限距离不能作为可用相似度或稳定排序承诺。候选finite政策可提供明确输入错误，但这是兼容差异/产品取舍，诊断不擅自放宽或宣布修复。保持GAP直至有效合同确认，测试观察应同时记录native接受和无效距离。

## 规范检查及限制

R5的真实接受事实已回流ingress合同；R6局部合同应补通用记录转换和派生type规则，分别列出完整formatter证明、非有限向量产品决定、真实完整adapter与native安全审计。此次仅诊断，没有改产品/主锁/旧冻结、没有提交或声称生产替换完成。root负责统一合同与memory更新，其他Agent工作区修改均保留。
