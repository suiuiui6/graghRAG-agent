# Git / GitHub 诊断快照交付核验

用户已明确要求提交并同步GitHub。沿用已审安全独立快照作为父提交，不推送master的旧凭据历史。拟交付分支为`codex/safe-snapshot-20261019`，安全父提交`0ae36f25c63cb9f483899992534af41bebf32089`。本记录在实际commit/push前写入；远端成功须另以真实提交和ref比较确认，不预报成功。

## 全量测试及分别双90

| 子项目 | 完整生产范围 | 测试结果 | 行 | 分支 |
|---|---:|---|---|---|
| backend | 104文件，未导入文件亦计入 | 1803 passed，pytest exit0；coverage导出exit0 | 14424/15499 = 93.0641% | 4744/5222 = 90.8464% |
| frontend | 29文件 | 当日17日完整122 passed、exit0；19日49输入全部hash相同 | 927/957 = 96.8652% | 853/913 = 93.4282% |
| rag_eval | 12文件 | 17日完整74 passed、exit0；19日22输入全部hash相同 | 1722/1742 = 98.8519% | 415/440 = 94.3182% |

后端最终输入前后完全相同，生产清单与报告文件集合相同，无缺项/额外项、excluded_lines=0。只读评审及包装不会改变生产输入。Windows仍为`audit-only-windows`，未启用或验证远端CI/分支保护。前端、rag_eval此次复核的是已有同快照全量证据，没有冒称19日重跑它们的测试。

后端实际命令由`publish-gate-20261019/backend/commands.json`记录：quality Python运行`coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=<证据目录>/backend.coverage -m pytest backend/tests backend/research/test_deepseek_scope_pilot.py -q --tb=short -p no:cacheprovider --basetemp <独立临时目录>`，再`coverage json`。PYTHONPATH依次包含隔离coverage运行库、本地langextract包根、backend；dotenv禁用、HF/Transformers离线。170.25秒，22个既有警告，无跳过/失败。机器报告、命令、日志、输入hash及完整覆盖范围已永久归档在[证据目录](publish-gate-20261019/artifact-manifest.json)。

## 本轮修正及评审

测试源遍历先跳过根tests树，避免遍历旧生成目录；离线网络守卫改为函数级monkeypatch，消除登录500的测试污染；研究库helper默认静默，CLI入口显式登记，导入时执行的默认参数/装饰器/注解仍禁止print。直接使用的openai/starlette已声明，当前锁与配置检查exit0。锁刷新仅registry/运输URL改变，208个版本和994制品文件名/hash未变。未修改生产认证逻辑来掩盖测试隔离故障。

新增报告、pilot、登记/预算拒绝及检索边界的真实行为测试，合成数据、本地SDK MockTransport，不调用provider。覆盖范围与门槛均未缩小。见[测试隔离评审](../review/2026-10-17-test-isolation-review.md)、[81项专项评审](../review/2026-10-17-new-behavior-tests-review.md)和[最终边界评审](../review/2026-10-19-final-test-review.md)。历史失败/修正证据保留于对应.tmp目录，不将专项通过等同全量验收。

## 安全、发布范围与限制

19日重新运行官方依赖扫描：backend完整206 registry锁包exit1，Chroma1.5.9五记录/四唯一GHSA，均无fix；rag_eval23锁包exit0/0，frontend345依赖exit0/0，uv lock --check exit0，审计前后锁/config无漂移。原始报告和范围、收据在归档dependency目录。包审计不代表完整原生运行库审计。

此前843候选中841 UTF8及1348个RustSec tar成员已完整扫描，5579命中全部逐条解释，未解释0；另两GB18030 JSON只读转码补扫0。19日补扫31个变化/新增文件0命中；归档和交付文档还须再次补扫并绑定最终发布字节。见[独立复核](../review/2026-10-17-publish-security-triage.md)。scanner无命中不等于隐私、版权或绝对无秘密保证。

发布仅采用显式清单。排除.env、个人配置、临时目录、未审研究结果/原始资料/新二进制、生成coverage目录、tsbuildinfo及dirty子仓库内容。保留既有两个gitlink，不能声称子仓库已审/同步；不将langextract本地dirty内容随根仓库上传。SQLite隔离候选与分页消费者证据保留，但尚未生产集成/迁移，现役Chroma公告不因源码上传关闭。本次仍为诊断快照，无部署。

首次后端重跑因账户额度耗尽导致自动审批无法完成，命令没有执行；额度恢复后已通过正常审批重试，未绕过权限。最终提交还需核对清单/暂存blob字节、三子项目输入hash、敏感祖先不可达和远端ref。

## 最终交付内容复核

[独立发布复核](../review/2026-10-19-final-publish-review.md)已关闭提交前内容及对象核验：903候选=833旧字节不变+70补扫，1165新增命中精确重构且未解释0；2832普通暂存blob全部读取重算，差异集合精确等于清单，两个gitlink不变、master非祖先。关键词自检2716行的8个实际detector匹配均有明确合成测试或拒绝默认值语境。独立复核原始三项生产范围、被测输入与两指标原始计数均通过。机器汇总同时归档`publish-gate-20261019/independent/verification.json`。加入该汇总与本次收尾文档后只补扫这些元数据并再核暂存字节，不改变任何被测输入；实际commit/push结果以Git对象及远端ref比较为准。
