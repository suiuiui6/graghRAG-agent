# 四个最终补充分支测试的独立评审

结论：本次范围未发现阻断问题。四文件专项实际 **105 passed，exit 0**；执行前后登记源码、四测试、conftest 与 pytest 配置哈希一致。此结论仅适用于所审测试，不代表全量后端、真实供应商集成、安全扫描或生产行/分支分别 90% 门槛通过。

评审者与实现者独立上下文；实际读取根 AGENTS.md、memory/index.md、2026-10-17 接续、requesting-code-review 与 verification-before-completion 技能。基线 HEAD `33adcc4cbd26bb6cd6b519c038fe2cad68baea59`，工作区含其他任务大量修改；本评审未修改源文件、测试、覆盖配置或父任务发布目录，仅生成独立验证产物与本报告。接续记忆由主任务负责人汇总，避免并发改写索引。

## 范围与行为检查

- `backend/tests/test_research_three_arm_edges.py`：真实生产 prepare/verify_registration/supervise/packet/scope/protection 逻辑，合成 AST 调用图仅作为解析输入，未导入或执行为生产算法替身。漂移、无凭据、缺收据、超时账本、未知费用、损坏账本、预算超额及不自动续跑均有行为断言。supervise 的子进程边界替身构造失败收据，明确不证明真实 worker 执行正确性。Gold、源和评审全部为临时合成输入，不读取历史研究结果得分。
- `backend/tests/test_research_isolation_edges.py`：真实本地 HTML 结构/范围解析、map→reduce、预算账本及快照拒绝。requests.Session.send 的本地响应替身保留真实请求构造、BudgetGuard 安装和记账；断言实际发送两次、只含目标范围、reduce 消费 map 输出、其余五题不调用。不是替换待测范围/预算算法。activation_state 用独立 monkeypatch context 恢复 cwd、sys.path、tempfile.tempdir、涉及环境变量及原 sys.modules 项，正向激活测试还精确比对恢复后的进程状态。物理快照 fixture 的假 exe/DLL 从未启动，仅测试文件选择/复制和拒绝策略；不能把它解读为原生 runtime 启动验证。
- `backend/tests/test_retrieval_remaining_behaviors.py`：真实 NetworkX、生产社区检索、排序/降级、真实 SQLite 持久化与竞争锁、RRF、metric rescue 和去重；无待测检索算法替身。ContendedLock barrier 明确使两线程都先经过缓存 None 外层检查，然后以真实锁串行初始化；测试断言对象同一和重新打开 SQLite 后值一致。
- `backend/tests/test_scope_pilot_validation_edges.py`：真实 prepare/run 本地拒绝，精确错误类别及无输出目录；凭据测试只读取注入映射，源、Gold、manifest 位于 tmp_path，pilot.py 仅复制现有公开代码。context、guards、九题矩阵、指令、范围过大和 CLI 静态错误均有明确断言。

四文件的 monkeypatch 均由 pytest 自动撤销；网络 connect/create_connection 均拒绝，两个文件额外拒绝 connect_ex。测试不创建 socket 子进程执行模型：supervise 子进程入口已替换为收据边界，其他 runpy 入口只走本地 help/静态验证。全程 `PYTHON_DOTENV_DISABLED=1`；supervise 的单一用例临时撤销该开关，但通过受限 dotenv_values 包装器仅允许 tmp_path/synthetic.env，fixture 自动恢复。无真实 .env 阅读和 provider 请求。这里的 socket 拒绝是本进程测试保护，不声称操作系统沙箱。

未见 skip、xfail、coverage ignore、缩生产范围、删弱已有断言或修改报告制造通过。对于部分无 match 的 ValueError 拒绝测试，变异分支和不生成 registration/evaluation 等副作用断言为辅助证据；不因此宣称验证了每一种错误文案。

## RRF 契约定点复核

有效规范 `integration/backend-api-architecture-v1.0.md:627-629` 与 `backend/evidence_trace.py:39-59` 一致：evidence-v1 使用 document_sha256→document_id→source_file namespace、object_type、span/source_item_id/original ID 与完整观测文本摘要生成身份。source_paths 不是身份；相同 chunk_id 本身不够。未显式指定 object_type 时，kg 推导 entity，bm25 推导 text，因此通常不合并。实现没有 source_hash 身份字段。

本次夹具显式声明 `source_file=one.json, object_type=entity`、相同原 ID 与文本，跨路径合并合理；保留 `len=1`、精确 `round(2/61,4)`、`source_paths=[kg,bm25]` 断言，不应改成宽松断言。

独立验证脚本另外检查三种对照：移除显式 object_type、改变文档 namespace、改变文本。三者均得到两个不同 evidence_id、各自精确 `round(1/61,4)`，全部 PASS。可后续把这些对照纳入长期测试；本评审未修改父任务待验测试。社区短语夹具以同 token score=2、较小 exact phrase 排在较大非短语社区前断言优先级，未要求生产不存在的分值加成。

## 实际验证与快照

最终绑定运行 UTC `2026-10-19T10:04:44.866951+00:00` 至 `2026-10-19T10:05:02.853400+00:00`，命令：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& .tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/final-test-review-20261019/verify.py
```

脚本为 pytest 子进程设置绝对 PYTHONPATH（coverage-runtime-py312-20261012、langextract、backend），`PYTHON_DOTENV_DISABLED=1`、HF_HUB/TRANSFORMERS/HF_DATASETS_OFFLINE=1，实际执行：

```text
python -m pytest backend/tests/test_research_three_arm_edges.py backend/tests/test_research_isolation_edges.py backend/tests/test_retrieval_remaining_behaviors.py backend/tests/test_scope_pilot_validation_edges.py -q --basetemp=.tmp/final-test-review-20261019/bound-pytest -o cache_dir=.tmp/final-test-review-20261019/bound-cache --junitxml=.tmp/final-test-review-20261019/bound-junit.xml
```

pytest **105 passed in 15.66s / exit 0**；wrapper（包括独立三组 RRF 对照）**exit 0**。首次相同专项亦 105 passed in 17.88s / exit 0；因首次未预登记输入哈希，最终结论绑定第二次完整复跑。

证据：`.tmp/final-test-review-20261019/{verify.py,receipt.json,bound-pytest.log,bound-junit.xml,identity-checks.json}`。receipt 保存实际命令、时间及逐文件 before/after SHA256，unchanged=true；receipt 自身 SHA256 `6ed3d7d90aba23370c89af6c88aeb0b3cd09c19010bf3cc4d7fe71e9a6d2eacd`。

| 测试文件 | SHA256 |
|---|---|
| test_research_three_arm_edges.py | 91181fb98073a64cd7d547470e71ddd97f45939911f9f5dcbe1776aaa56f9dbd |
| test_research_isolation_edges.py | 878bdf6549e87b3bd76664205bb50a0e71544a58bee064c154bffd6e55f3d7c2 |
| test_retrieval_remaining_behaviors.py | e6860bc698a686d625679e3f5aac602e96109587e0bcbc1bec3dcd3ba79eb8c9 |
| test_scope_pilot_validation_edges.py | 895373c7b6fcc17580f0623ad2ec138fe141d2c4342b4123e4d8e8e1c781c310 |

下一步由主任务结合当前最终代码快照全量测试、固定完整生产分母两项覆盖率和安全门槛决定能否提交。本评审无 commit、push、部署或全量门槛结论。
