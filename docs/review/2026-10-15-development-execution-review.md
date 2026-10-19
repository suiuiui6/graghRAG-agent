# 开发隔离与预算执行独立审查

2026-10-15。只读审查主消费者、安全父进程、隔离适配和预算 guard；独立运行离线专项与收据哈希核验。未读 `.env`、Gold、answers，未调用真实 API/生产索引。

## 审查总结

最终定点复核：预算守卫 R2、实际 SDK httpx2 漏拦以及结构 R1（含分片标题）均已关闭。**PASS_FOR_BOUNDED_PUBLIC_DEVELOPMENT_PROFILE：未关闭问题 0 Critical / 0 High / 0 Medium / 0 Low**；在最终隔离目录绑定下列快照、前置额度不变的条件下，可进行用户已授权的公共开发资源测定。该结论不是语义评测或产品发布放行。

## 问题清单

### 🟠 High R1 续：带字体的数字片与缺字体的标题片

- 位置：`backend/research/development_structure.py`，`build_pdf_structure` 数字标题拼接分支。
- 问题：`<text font="Bold">2.</text><text font="missing">Second</text>` 中数字片有字体，后续片缺字体，拼接失败后 `_number('2.')` 为空直接跳过。diagnostics 仍空，选择前一章仍 RESOLVED 越界。
- 独立实际复现：正式候选环境，陌生两章 canonical `1. First\nbody\n2. Second\nexcluded\n`，得到 `[] RESOLVED`，exit 0。已通知 coder 修复。
- Before：`if not number: continue`。
- After（建议）：对有字体且 bold 的数字标题候选，不能拼成完整标题也保留不确定诊断；完整已知 normal 字体正文编号仍跳过。
- 最终修复已核：有字体 bold 数字片不能组成完整标题时产生 INCOMPLETE_HEADING_FRAGMENTS；数字候选缺字体产生 MISSING_FONT_EVIDENCE；XML页集合缺失/重复均拒绝。独立正式候选环境复跑四文件（development_structure、development_scope、scope_v2、local_scope_v2）：**82 passed in 5.98s，exit 0**。重新只读计算2来源/2结构sidecar/6非Gold范围结果全部 MATCH，exit 0；原跨度不变。R1关闭。

## 已关闭问题与执行证据

1. 预算 `_finish` 对顶层 JSON、choices、message、content 均有类型/非空验证，异常结构进入统一 FAILED_CLOSED。实际SDK模块从 `openai._base_client` 唯一识别，guard 同时包裹 requests、httpx1 与 SDK httpx2 的 sync/async send。install 获独占锁后重读账本，避免旧 guard 覆盖先前累计值。未知请求保留 UNKNOWN，不以 0 代替。
2. 正式候选 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_development_budget.py backend/tests/test_development_isolation.py -q -p no:cacheprovider --basetemp .tmp/resume-final-guard-20261015b`，PYTHONPATH=`backend;langextract`，TEMP/TMP 位于工作区：**29 passed in 6.04s，exit 0**。包括真实 SDK 的 MockTransport wire、损坏响应、敏感输出、空内容/usage/截断闭锁和锁后状态重读。首次 PYTHONPATH 只有 backend 时 27 passed/2 failed，原因是根目录 namespace 包遮蔽 editable LangExtract；正确显式源码路径复跑全部通过，未改代码来隐藏失败。
3. 独立核 `.tmp/isolation-coder-native-preflight-02/artifacts/preflight.json` 与全部 snapshot 文件及八个有效模块路径/哈希：**40 simulated requests，443857 request JSON bytes**；每条实际 SDK 序列化记录 model=flash、thinking disabled、max_tokens=4096。sdk_transport_module=httpx2。该预检只生成空抽取，本审只复核产物与哈希，没有把它作为真实 token/抽取正确性证据。
4. 契约首实际请求前已修订到 72 次总尝试：index40/P018/A14；229376 声明输出 tokens、1.2M 完整 request JSON bytes、1800 秒总窗口。Guard默认一致；A每调用45秒、index子进程600秒、P0每题120秒，父进程按全组剩余时间控制。执行中不能抬额度或复用失败未知成本账本。
5. A 的输入来自 sources.json/source SHA、questions.input.json 固定四字段以及原件结构，原 assemble_scope 的实际 mappings 按8000字符切 exact slices；map/reduce沿用先前冻结指令，未读 Gold或按目标答案裁剪。局部范围成功不证明语义完整性。
6. 安全父进程只在内存解析 `.env` 并注入子进程 key，完整子进程 stdout/stderr 捕获内存后丢弃，仅保存受控状态白名单；模型 guard 不保存headers/原始错误正文，成功回显 key 会闭锁并拒绝返回下游。代码与静态schema复制、有效模块__file__核验、独占backend CWD/TEMP/cache/KG/docs store、HF offline及前后snapshot核验符合本轮审计；Windows仍为 audit-only-windows。
7. P0明确为真实document_id授权KG-only路由函数与管理员 Request fixture，非 JWT/中间件/完整HTTP验收。入库是canonical格式桥接进入原PDF LangExtract→grounding→KG组件，非重新执行MinerU；输出分别保留native grounding与exact source interval，不伪造layout或grounded状态。

## 已审执行模块 SHA256

```text
development_budget.py AD49ACE9E8D70081F0B0FDC4258B6E936803EEEF6D0A4CF9F6D5C1A99D331A03
development_isolation.py 8144EF633F3A7CB8E897E6C11115211A7D31B6D9C970AD88264C8386272E2410
development_profile_cli.py 584CAF720F10215C9EC0B0C673F75B99EBF7F6694A3452B8AB19626344BB49EC
development_run_authorized.py A5B004BC5E1BFF1DBE49B1F8A0316CC49337725C0D85EBB3CF3E6C113F370851
development_structure.py 951DB304B00918B13719FB8F9383D8AA9EDEF17D1F2994F4575BD339C81AA004
development_scope.py 987DA1F223DC3EC9D4D0021F55395BD4858BFF83B3BD874670D6820454B525F2
```

## 优化建议汇总

最终 wire delta 独立复核：request严格UTF8解码并解析，原始字节及解析JSON均查实际key后才保存request_wire_utf8；response只在COMPLETED且无key时保存response_wire_utf8，其他情况不保存原wire。原SHA与字节数现可复算，解析对象与wire一致。新增空白/Unicode转义checksum测试有行为断言；同一正式候选环境、PYTHONPATH与workspace TEMP配置独立复跑预算/隔离两文件，basetemp `.tmp/resume-wire-guard-20261015`：**30 passed in 7.75s，exit 0**。其余执行模块未变；上述PASS保持，绑定更新budget哈希。

1. 主审执行前重核最终隔离准备目录绑定上述源码和预算；R1及实际六题的独立定点复核已完成。
2. 真实执行后独立核全链收据、usage、请求/回执模型、map→reduce与grounding映射，任何成本未知/原生no_data分别如实记录。
3. 本专项不证明语义缺口、留出效果、产品全量覆盖或安全发布准入；无commit/push/deploy。
