# 独立 API 适配器验证记录

2026-10-07。仅研究适配器，不代表生产端到端测试或论文方法验证。

实现文件：`backend/research/deepseek_scope_pilot.py`、`backend/research/test_deepseek_scope_pilot.py`。

TDD实现者记录：初始15个缺模块失败；凭据选择修订也记录失败后修复。主agent重新执行：

```powershell
backend/.venv/Scripts/python.exe -B -m pytest backend/research/test_deepseek_scope_pilot.py -q -p no:cacheprovider
```

最终修订后主agent再次执行，退出0，28 passed，1 warning（现有pytest配置timeout选项未识别）。网络仅在httpx MockTransport边界替代，不读取真实`.env`，无真实API请求。

规范审查：独立spec_reviewer PASS。审查发现并修正凭据选择范围，补充真正无效JSON响应测试。审查者再次独立执行20项测试通过。安全/代码质量审查发现嵌套响应结构缺口，增加8项回归检查后再次审查：READY，无剩余Critical/Important。非阻断备注：失败时CLI可能退出0，必须以journal与final-statuses判断结果。

真实资料dry-run：初次`api-runs/20261007-dryrun-v1/`，最终代码重新准备`api-runs/20261007-dryrun-final/`。27计划条目全部NOT_ATTEMPTED，模型固定v4pro，B1/B2/B3各9条；最大8192 UTF-8源字节；统一排除1个参赛编号行，payload未含该编号。未调用模型，不可作为回答正确率。

生产文件并发变化：初始API preflight之后generator指纹又改变，旧记录保留`api-freeze-preflight-v1.json`，最终API manifest记录本次变化与适配器指纹；重冻结时API请求数0。无生产修改、回滚或历史离线结果覆盖。若最终冻结后再变化，调用前守卫会停止，不静默更新。

测试遗留：实现者早期pytest试验留下不可访问的`backend/research/.pytest-temp`；未修改ACL或进行危险清理。后续自定义测试临时目录在工作区内按精确路径清理。

真实调用后最终核验：27计划/27调用意图/27SUCCESS；全部payload字符跨度与原文逐一相同，manifest及15个guard无漂移；所有run目录实际凭据扫描未命中，payload未含参赛编号；状态YAML有效且调用数27。此审计没有新增网络请求。再次执行完整测试：28 passed、1项同样的现有warning，退出0。学术暂定裁决与Gold争议不被软件核验取代。
