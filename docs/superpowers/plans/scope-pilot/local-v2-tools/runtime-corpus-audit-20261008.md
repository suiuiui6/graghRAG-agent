# 真实运行、语料身份与上下文来源核验

记录日期：2026-10-08。性质：只读工程核验，不是模型实验或学术阶段验收。
对应元数据：`runtime-corpus-audit-20261008.json`。M2 保持开放，历史 M4 P2 的 189 测试记录保留，本轮未重跑。

## 裁决

| 门禁 | 结果 | 已证实范围 |
| --- | --- | --- |
| 本项目真实运行身份 | UNKNOWN / BLOCKED | 8001 属于另一项目 OCR 进程链；8000 未观察到监听。不能据此断言本项目不存在任何其他端口实例。 |
| 磁盘冻结身份 | PASS | 当前 15 个生产/合同文件、3 个原文和 62 个历史结果与冻结指纹一致；只证明磁盘，不证明进程加载版本。 |
| 原生语料身份 | PARTIAL | Chroma rag_docs：512 维、1440 条；1235 条满足至少 20 字符检查条件；D1 31 块唯一逐字匹配。 |
| 原文坐标映射 | 不通过直接使用 | D1 仅 1/31 原 stored span 有效；其他 30 条不自动修复。 |
| 同版本实际模型上下文 | NOT_CAPTURED | 未取得 9 个 v2 问法的实际可见序列化上下文；本地块和旧回答不能替代。 |
| 真实 B0 | NOT_RUN | 未启动服务、未生成、未调用 API。 |

## 运行身份

02:30:38 UTC 的 netstat 成功返回 `127.0.0.1:8001 / PID 1772`，未观察到 8000 监听。
02:31:16 UTC 的只读 CIM 核验：PID 1772 的父进程 PID 43352 来自另一项目 `services/ocr-provider/.venv/Scripts/python.exe`，两进程白名单入口均为 `uvicorn app.main:app`。
本项目磁盘启动入口为 `uvicorn server:app`（backend/start.sh，端口 8000）。
未向 OCR 服务发 HTTP 请求、未读其项目文件或停止它。venv launcher 使用全局 Python 子进程不构成环境污染证据。

沙箱中的 Get-NetTCPConnection/CIM 未提供有效进程证据；空列表不作为端口不存在证明。最终依据成功 netstat 与经批准只读 CIM。
进程哈希和安全元数据见 JSON；不导出原始命令行、环境变量或凭据。真实 GraphRAG 的 PID、cwd、加载代码、模型、prompt、配置及内存索引均未知。

## D1 坐标系诊断

按 stored start 排序的 31 块直接拼接长 22282；冻结 LF 原文长 22366。
31/31 stored spans 对该拼接文本逐字有效，但仅 1/31 对原文有效。
原文候选块之间有 30 个间隙，共 84 Unicode codepoints；25 个间隙仅空白、5 个含非空白。
差值从 0 增至 84，共 31 种，不支持全局 +1。全部 31 行块指纹、stored/candidate spans 已保存在 JSON；
`matched_01` 等只是本次诊断编号，不是假冒 native chunk ID。

坐标单位：LF-normalized Unicode codepoint 半开区间 [start,end)。
candidate_original 是逐字匹配候选，不能冒称原生产已验证坐标或真实模型上下文。
当前 worker.py:603–633 的 item text strip + 累计长度与此现象一致；历史入库 producer 未确认，故根因解释只标 AI 推断。
未修改原索引，也未把这个工程缺口包装成可推广方法贡献。

## 语料命名与更正

Chroma 元数据缺 document_id/document_sha256/span_verified。
四组 source_file 标签的 hash、计数、docs-store 文件名连接计数见 JSON；文件名连接仅为 LABEL_JOIN_ONLY_NOT_HASH_VERIFIED。
docs-store 83 条；D1 标签 test.pdf 与 BM25/table 标签 paper.pdf 无精确 filename join。这不证明语料不存在。

更正截断路径检查：`doc_ingest_f` 不存在并不能说明完整 ID 不存在。
实际 `doc_ingest_f7af6ada` 有 nodes.json/edges.json，并有 1 条 docs-store ID join；
尚无证据将它与冻结 D2 原文 hash 绑定，不擅自认作 D2。
D1/D2 原文 hash 各只匹配对应 ingest_2/ingest_f 的 full.md；D3 不属于 MinerU 原文资产，该目录零匹配正常。
D2/D3 在本次 Chroma 整段逐字方法下零匹配，不表示未入库、检索失败或模型失败。

BM25 3 段、table 2 行的磁盘记录不代表运行实例已加载；结构化表行不能直接套全文 matcher 判断缺失。

## 上下文与启动边界

runtime_cache 5 个短字符串；rewrite_cache 151 个 JSON，无完整 v2 问法精确命中，也无 serialized_model_context 字段。
限定缓存/候选文件检查不等于全系统不存在其他 capture。本次原生模型可见上下文仍未捕获；
evidence_trace 的 request-local helper 不等于已存在持久化运行证据。

现代码启动会恢复索引、稀疏表格回补（阈值 5，磁盘现 2 行）、模型预热及备份/清理/健康探测。
这不是只读核验替代方案，故未启动。若使用隔离副本，必须声明隔离实例及与 native B0 的差异，不得冒充原运行实例。

## 复现与证据边界

本项目 Python：backend/.venv/Scripts/python.exe，执行带 -B。
基础复现：`backend/.venv/Scripts/python.exe -B -m backend.research.local_scope_v2 prepare-b0`（从仓库根）。
扩展诊断通过本地 research loader/map_text 和 SQLite mode=ro、query_only、BEGIN 读取。
未导入生产模块、加载模型、安装依赖、读取 .env、发 HTTP 或模型 API 请求。
Chroma 主库与 WAL/SHM 在本次读取前后 hash 相同；cache hash 仅为观察快照，不能作为整个本轮前后不变证明。
独立工程 debugger/reviewer 复核了主要结论，截断 ID 的不当泛化已剔除；没有开展学术专家阶段验收。

## 唯一下一步

先确认“禁止外联、保留原索引”的隔离运行身份/上下文捕获方案及启动副作用边界，再申请实际启动。
本次核验不授权真实生成/API 批次；M2 仍开放，论文贡献、泛化性和期刊层次均未确定。

