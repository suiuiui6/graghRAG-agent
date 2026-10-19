# 错误策略源码遍历修复

根因：`backend/tests/test_error_handling_policy.py::_sources` 声明不含根 tests 源码，但先递归 tests 全树再过滤文件；生成测试树导致完整回归超时。修复仅在入栈前剪枝 `BACKEND / "tests"`，原过滤、断言、超时和覆盖配置均保持。没有遍历或清理旧测试树，没有排除 research 或任何新增生产文件。

新增回归 `backend/tests/test_error_policy_source_walk.py` 在独立小目录中 spy `Path.iterdir`，禁止进入根 tests 目录；另验证未导入根生产文件、research 源码及 research/tests 下源码仍在既定范围。

实际使用 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -m pytest`，均 `-q --tb=short -p no:cacheprovider`，`--basetemp` 分别使用 `.tmp/publish-retry-walk-20261017/` 的 `red-temp-2`、`green-temp`、`regression-temp`。日志同目录 `red.log`、`green.log`、`regression.log`。

- 修复前仅新回归：exit 1，1 failed / 1 passed，失败明确为进入根 tests 目录。
- 修复后仅新回归：exit 0，2 passed。
- 修复后新回归＋原全部守卫：exit 1，6 passed / 1 failed，1.70 秒；真实失败为 research 中 18 处 print，不再是遍历超时。该失败保持并交回主任务处理。

首次测试因模块导入方式 collection error（exit 2）；随后改为按相邻文件路径加载，以上有效红绿均使用最终测试加载方式。未声称整体守卫通过、后端全量通过或覆盖率达标。未提交、推送或部署。独立评审及完整验收由主任务继续。
