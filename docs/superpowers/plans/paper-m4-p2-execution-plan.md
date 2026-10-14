# M4-P2 Implementation Plan

**Goal:** 在已有生产链增加请求级可选证据、实际上下文与答案转换追踪，不生成论文结果。

**Architecture:** 复用已确认 P2 合同。独立 `backend/evidence_trace.py` 负责版本化身份、来源合并和请求内证据账本；retrieval 在投影前固定身份并记录每个筛选面；prompt 在格式化/截断时记录实际可见字符串与映射；generator 记录模型调用和确定性路径的不同证据及转换链。普通响应不含全文。

**Tech Stack:** 项目已有 Python 3.12、dataclasses、hashlib、pytest、FastAPI、BM25/SQLite；不安装依赖、不调用远程服务、不提交或改分支。

## 执行清单

- [x] 身份/RRF：新增失败测试；文档命名空间与缺 ID 稳定哈希；相同位置多来源合并、内容冲突保留；固定同分次序。身份缺文档/span 标记 unknown，不假装精确定位。
- [x] 检索面：投影保留追踪白名单；请求配置 `include_evidence_trace=false`；记录 normal/rescue、pre-rerank、post-rerank、retrieval-final 以及被删除对象。旧 citation label 是兼容映射，不作为 canonical identity。
- [x] prompt：测试混合文本、KG 格式、超长头部、domain hint、截断边界；记录 messages/context 哈希及真实可见片段；序列化位置与原文位置区分。保留字符估算，不声称 tokenizer 精确预算。
- [x] 答案链：在 provider 解析处保存未 strip/未修补输出；记录 length/citation warning/repair/complete/supplement；确定性拒答/纠错 raw/context=null，单列实际使用的 decision_evidence；provider 失败 fallback 不冒充原始模型输出。
- [x] API：trace 仅显式打开时返回；query 4000 字符响应截断也记录为独立阶段（静态核对，无专门超长端点测试）；显式追踪不得进入无追踪能力的 legacy fallback；真实 BM25/SQLite 端点集成验证。
- [x] 验收：P1 与选定回归、静态检查、只读复审；更新规范、P2 验证记录与 SCI 状态。保持 M4，P3 和模型实验未执行；M2新颖性复核状态不改变。

测试统一用 `backend/.venv/Scripts/python.exe`，设置 HF_HUB_OFFLINE、TRANSFORMERS_OFFLINE、PYTHONDONTWRITEBYTECODE；TEST_ONLY 数据不进入历史 ground_truth/raw_runs。对于模型分支，替换网络边界响应而不是证据/追踪主逻辑，不宣称模型集成通过。
