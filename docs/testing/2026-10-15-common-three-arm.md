# 三臂共同配置执行器离线验证

```json
{
  "date": "2026-10-15",
  "command": [
    "D:\\graghRAG-agent\\.tmp\\backend-quality-venv-20261012\\Scripts\\python.exe",
    "-B",
    "-X",
    "utf8",
    "-m",
    "pytest",
    "tests/test_common_three_arm.py",
    "tests/test_development_budget.py",
    "tests/test_development_isolation.py",
    "-q",
    "--tb=short",
    "--basetemp=../.tmp/common-three-arm-final-delta"
  ],
  "exit_code": 0,
  "source_sha256": {
    "backend/research/common_three_arm.py": "d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e",
    "backend/tests/test_common_three_arm.py": "9af66741db868692944ba951bbf3f503b97c093a1161663fba5deae01e4dfff9"
  },
  "stdout": ".......................................................                  [100%]\n55 passed in 8.21s\n",
  "stderr": "",
  "real_provider_calls": 0,
  "prepare_root": "D:\\graghRAG-agent\\.tmp\\common-three-arm-coder-offline-20261015",
  "prepare_exit_code": 0,
  "prepare_limitation": "Prior offline prepare; final formal root must be freshly prepared from final runner by root agent.",
  "runtime_scope": "offline coder inspection only; formal reviewed registration still required"
}
```

只验证研究执行器，不替代产品全量覆盖/安全验收。未读取真实密钥、未联网、未调用模型、未提交。

本轮新增25专项行为测试，复用冻结transport与隔离模块30回归。覆盖54顺序与全源Unicode切块、P0原生1+2路径及global mode默认false、请求/字节/实际token额度、资源cap续行与unknown/timeout停组、54结果分母、SDK实际httpx2、启动deadline、全局177发前额度、缓存路径、环境allowlist、A范围每次重算及登记比对、map原文与标题元数据输入分开记录。

准备入口从历史145源码和KG复制新运行根，核KG与历史executed-isolation一致，重写新docs_store路径，注册契约/计划及依赖身份。每子进程使用allowlist环境、新HOME/APPDATA/TEMP/HF离线及显式temperature0.0。真实运行仍由根代理在独立复审通过后执行。

最终源码另行离线 prepare 验证成功：.tmp/common-three-arm-coder-final-check-20261015，退出码0，54单元/177路径尝试；含最新治理SHA、共同预算字段、KG历史归档一致性与依赖身份。该目录未真实执行；根代理将另建正式profile。
