# 五项 P0 修复核验（2026-10-12）

> 后续用户要求的双覆盖率及漏洞扫描已执行，见 [实测报告](2026-10-12-coverage-security.md)。后端65.49%行/54.09%分支，未达标；当前/锁定依赖和前端均有漏洞发现，仍禁止提交。以下保留P0修复交付时的测试及工具能力记录，不代替该后续结果。

本报告更新历史评估 #1/#2/#3/#4/#50；其余条目未在本次修复后重新评定。五项原风险均已在本地适用范围关闭，不表示完整企业能力、供应商集成或提交门槛通过。实现保留在未提交工作区。

## 状态与证据

| 编号 | 状态 | 当前代码证据 | 实际测试证据 |
|---|---|---|---|
| #1 认证与资源授权 | 已修复 | `backend/auth.py:create_auth_middleware` 默认拒绝；`middleware/jwt_middleware.py:_secret/decode_token/create_jwt_middleware` 校验安全密钥、issuer/exp/sub/type、当前用户/角色、托管key owner与方法权限；`services/resource_access.py` 核验owner/真实项目成员；server顺序为JWT→认证→租户→资源。入库身份来自服务端。 | `test_p0_authorization.py`：默认密钥伪造、refresh、撤权/禁用、key撤销、读key禁止删除、伪造项目、旧资料仅admin；`test_p0_resource_routes.py`：真实server中间件、owner入库、状态/文件越权、CORS与精确公开脚本。 |
| #2 查询未限定文档 | 已修复 | `routes/query.py:query` 检索前授权、独立图快照；`services/document_snapshot.py` 注入真实doc/version、读取active版本；`routes/rag_query.py:_generate_scoped_rag` 受限KG、拒绝旧session/无法隔离来源；摘要传递同一Request。空图直接no_data。 | 路由测试在生成边界检查只看到A、不见B；外部文档请求在模型前404；active v2只读当前版本；全局初始化不得触达；无授权数据不调用模型；旧session409、显式vector503。 |
| #3 MinerU目录冲突 | 已修复 | `routes/ingest.py` 完整UUID；`worker.py:_call_mineru_api/_call_mineru_local_file` 完整安全task_id目录；`mineru_client.py:download_and_extract` 独占mkdir、独立working、校验后rename result；`server.py:_iter_mineru_runtime_sources` 兼容新发布布局、拒绝working/链接。 | `test_p0_mineru_isolation.py` 同前缀并发、残留拒绝、非法ID、失败不发布；真实合成ZIP缺文件/坏JSON/非数组/链接失败，完整包发布；`test_p0_runtime_sources.py` 新旧恢复和真实链接。 |
| #4 无关解析缓存回退 | 已修复 | `worker.py:_find_cached_mineru_output` 恒None且解析链不调用；ingest显式true先400，不能将旧产物入库。 | 默认/显式true且供应商边界失败时旧缓存不变，抛失败；API true拒绝且上传目录字节不变。`test_worker_upload_fallback_chain.py` 已改为禁止复用的行为断言。 |
| #50 危险删除 | 已修复 | `routes/documents.py:delete_document` 先授权存在再解析精确登记资产，移除前缀扫描；`contained_asset` 拒绝越界/symlink/junction；失败保留metadata，成功使查询缓存失效。 | 未知doc_404且全部原件不变；合法删除不影响相似名/另一文档；越权404；越界、真实symlink与Windows junction409且其他资产保留。 |

## 实际执行与快照

主机 Windows，Python `backend/.venv/Scripts/python.exe`，仓库根运行。设置 `PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。本地API测试经批准在沙箱外执行，解决Windows沙箱socketpair阻塞；没有绕过审批。

基线 HEAD `46b202c3e400741fd569f024412c0745f224a538`。最终后端源码/测试/依赖文件141项哈希清单见 [snapshot](2026-10-12-p0-code-snapshot.json)，聚合SHA256 `0d00e6ef1001c5e9478e9dd2f3af10e7425934ae08aa7174a873f3aa417623c3`。这是代码快照，不是覆盖率分母。

```powershell
& backend/.venv/Scripts/python.exe -u -m pytest backend/tests/test_p0_authorization.py backend/tests/test_p0_resource_routes.py backend/tests/test_p0_mineru_isolation.py backend/tests/test_p0_runtime_sources.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/p0-final-20261012
# 84 passed, 1 warning, 9.41s; exit 0

& backend/.venv/Scripts/python.exe -u -m pytest backend/tests -q --tb=short -p no:cacheprovider -o faulthandler_timeout=60 --basetemp backend/tests/_sandbox_tmp/p0-full-final-20261012
# 705 passed, 22 failed, 5 warnings, 42.69s; exit 1
```

[P0最终日志](2026-10-12-p0-final.log)、[全量最终日志](2026-10-12-p0-full-backend-final2.log)。前一次全量691/33是中间快照，已被此结果替代，不能混算。旧契约适配192通过、追加集成/恢复39通过、终态隔离5通过的独立命令见 [适配报告](2026-10-12-p0-compat.md)，与全量有重叠，不累加成独立用例总数。

RED→GREEN：默认secret/claims 4失败，撤权/type/空授权4失败，CORS/widget2失败；runtime7失败、发布校验6失败，均见同目录对应red日志与最终green。早期用户夹具4个setup error不充当漏洞红测；修夹具后有实际4失败日志。独立静态首审的撤权、空图、type、产物校验及junction意见已关闭，见 [复审](../review/2026-10-12-p0-code-review.md)。主负责人对14个本轮生产文件AST解析退出0，相关路径git diff --check退出0；未声称ruff通过。

## 全量失败与剩余优先级

| 优先级 | 剩余工作 | 本轮证据与限制 |
|---|---|---|
| P1，发布/提交阻塞 | 收敛全量22失败 | 18项依赖缺失的`research/isolated_guard.py`；1项研究CLI print违反库规范；2项`local_scope_v2`的冻结完整性及BM25产物计数不匹配（172≠3）；1项研究测试pytest导入未满足供应链检查。冻结失配可能随本轮生产修改产生，不能全部称为既有无关失败，更不能直接改冻结值掩盖。需由研究任务重新核验并做合法再冻结/隔离夹具。未修改研究实现或删弱断言。 |
| P1，提交阻塞 | 建立并测量全量行/分支覆盖率、漏洞扫描 | 当前venv缺coverage/pytest_cov/pytest_timeout/ruff/pip_audit/bandit。行、分支原始计数均未测量，≥90%未证明；漏洞扫描未执行。禁止commit/push。 |
| P1 | 后续持久化与任务终态、真实供应商/功能验收 | 原评估#12–18等仍按初始审计排队；本轮仅补安全相关缓存失效与时间处理，不宣称全部关闭。真实MinerU/OIDC/生成服务及前端登录工作流未验收。 |
| P1 | 全索引资源归属、绑定会话与历史归属迁移 | 当前非admin/指定doc/project仅授权KG；其他全局资料接口限admin。显式vector/table等503，旧session409；这是安全收口，不是完整多租户体验。后续须独立设计索引doc身份及可信管理员迁移。 |
| P1/P2 | 其余原评估条目 | 仍见历史核查的正确性、引用、解压/下载、安全、就绪/部署和体验优先级，不因五项修复自动降级。 |

## 集成证据边界

用户/tenant/key/doc/task JSON、临时原件、图谱、版本与FastAPI中间件实际执行；模型/云供应商只在边界替代。MinerU真实合成ZIP与文件系统发布实际执行，下载用本地复制，沙箱不允许Git/MSYS unzip命名对象，测试解压适配为独立Python zipfile进程；不等于公网下载、生产unzip或MinerU云端验收。原件链接测试实际创建symlink与Windows junction；未在真实uploads做危险删除复现。

规范已回流到后端API、企业蓝图及MinerU组件规范；归档摘要见 `docs/troubleshooting-archive/2026-10-12-p0-security-fixes.md`。Windows治理执行为audit-only-windows。未提交、未推送、未部署。
