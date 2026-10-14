# 双覆盖率90%整改：最终阶段证据与剩余优先级

状态：三个相关子项目双指标达标；整体安全门槛仍阻塞，向量存储替换设计/MVP已获用户授权且进行中。未提交、推送、部署；当前audit-only-windows。

## 最终快照验证

| 子项目 | 固定第一方生产范围 | 全量测试 | 行原始计数 | 分支原始计数 |
|---|---:|---:|---:|---:|
| backend | 90 Python文件，含未导入源码 | 1496 passed /14warnings，exit0 | 12698/13568=93.5878537736% | 4154/4584=90.6195462478% |
| frontend | 29文件，含正式public/chat-widget.js | 122 passed，exit0 | 927/957=96.8652037618% | 853/913=93.4282584885% |
| rag_eval | 12 Python文件，含CLI/build_ground_truth | 74 passed /1warning，exit0 | 1722/1742=98.8518943743% | 415/440=94.3181818182% |

分别按整数比较判断，不使用coverage混合总分或显示四舍五入。backend配置exclude_lines/partial_branches为空，excluded0，范围与源码清单相等；前端包括真实发布IIFE，测试自身非生产；rag_eval完整12文件已独立核实。上游langextract第三方子模块与历史MVP/可视化原型不冒充本轮第一方发布范围，完整范围依据见前端及coverage范围独立审查。

backend最终证据`2026-10-13-to90-final-r2*`：完整命令为候选Python通过`coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/2026-10-13-to90-final-r2.coverage -m pytest backend/tests backend/research/test_deepseek_scope_pilot.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/to90-final-r2-20261013`，关闭dotenv及模型网络，Windows loopback经正规require_escalated审批运行。pytest与JSON导出exit均0。171输入前后hash一致，快照`54fdbfdbf20799812290a7eb4988a0d4c0091ae141c4fa99dc276511b24709c9`；四项受保护runtime产物hash一致，当前输入drift0。前一final全量虽1459passed，运行中测试变化导致hash不一致，仅历史诊断，不作最终证据。

前端53输入hash一致，build/frozen/完整345依赖官方audit/两组真实Chromium验证均exit0，0公告；详见`2026-10-13-widget-upload-readiness.md`及`frontend-widget-upload-20261013/`。rag_eval22输入/12生产无漂移，锁及实际安装23registry相等、全锁审计0公告；77保护项仅规范回流有意改动1文件，Gold与结果未改，详见专项及独立审查。

## 本轮修复核实

| 项目 | 状态 | 代码与测试证据 |
|---|---|---|
| 全第一方双覆盖率不足 | 已修复（上述三子项目范围） | 固定配置与原始JSON，不删弱旧断言；最终各项全量日志 |
| DuckDB条件SQL注入/非法limit/资源边界 | 已修复 | backend/table_index.py；test_table_security_readiness.py，真实DuckDB；最终Bandit完整90文件中危0/高危0 |
| KG保留策略删除active/版本号复用/并发与清单失败 | 已修复（本地范围） | kg_store.py、services/lifecycle.py；真实FileLock/临时目录/故障恢复及高水位99专项；独立178阶段与最终专项 |
| 索引快照截断、读失败写空及测试写真实runtime | 已修复 | index_registry.py、tests/conftest.py；6001行真实DuckDB独立探针、失败保留原bytes、最终四项runtime稳定 |
| Widget来源HTML注入与Upload晚回调竞态 | 已修复 | public/chat-widget.js、UploadPage.tsx；红4失败、完整122绿及真实Chromium注入探针；独立18专项 |
| 跨组织归档及飞书告警构造500 | 已修复 | routes/tenants.py、routes/bot.py；test_auth_tenant_readiness.py，红31pass/5fail后绿；最终全量纳入 |
| 飞书缺签名放行、签名密钥错误、URL验证绕过 | 已修复（消息认证范围） | routes/bot.py、services/feishu_client.py；官方SDK模式矩阵；143作者专项、111独立专项hash稳定；最终1496全量 |
| 飞书陈旧签名/重复请求防重放 | 未修复 | timestamp123同签名重复两次200实际探针；不把合法签名等同新鲜请求，尚未承诺窗口/去重 |
| Chroma包级4唯一GHSA/5原始记录 | 部分修复 | 移除未使用HTTP服务/任意配置边界；pip-audit仍exit1且无fix_versions，不能清零；替换设计/MVP进行中 |
| 历史研究版本冻结漂移 | 待验证（实验准入仍阻断） | 冻结不回写；软件测试验证真实DRIFT与禁止执行，不能作为新实验身份通过 |
| 镜像、真实供应商、远程CI/分支保护 | 待验证 | Docker daemon不可用；供应商边界替代仅验证软件，未执行远程CI，未部署 |
| 历史B608豁免 | 已不适用 | 已撤销CI --skip B608并更新历史台账；完整扫描低危仍136/exit1，中危+中置信门槛扫描exit0 |

独立报告`docs/review/2026-10-13-readiness-final-independent.md`验证前端53输入与29分母、111后端专项、18前端专项、真实6001行及失败保留；发现并最终关闭飞书鉴权High。`2026-10-13-rag-eval-readiness-review.md`独立74通过并核实12文件/22输入/23依赖；指标规范漂移回流关闭。上述审查只覆盖其列明范围，不能担保所有历史产品逻辑无缺陷。

## 剩余优先级

1. P0安全供应链：按用户已选路线完成向量库替换能力盘点、独立锁MVP及设计评审，再确认集成/迁移计划。当前不得移除扫描记录、ignore公告、擅自覆盖旧向量库或降级检索能力来清零。
2. P1回调安全：防重放需明确时间窗/重复事件语义、多进程共享状态及恢复策略，补红绿与消费者验证；真实飞书接收/加密体支持单独验收。
3. P1交付：Docker实际构建、可信CI完整两指标范围门禁与保护分支，以及真实供应商验收。现有CI文本不能当部署成功。
4. 研究准入：对冻结身份作独立版本决策，不修改历史hash伪造一致；不授权新实验或科学结果重写。

低危静态发现136项仍保存原始报告，不把低于CI严重度阈值称为漏洞全修。用户原评估62项逐项审计保持原报告身份，本阶段表是新增/受影响整改状态，不替代其余条目复核。
