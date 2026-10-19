# 简单输出约束独立实施审查

审查总结：通过，可按冻结登记执行54单元开发复验。上一轮两项高风险冻结前条件已关闭；当前0 Critical、0 High、0 Medium阻断，1项Low清理建议。此结论不代表开发语义效果已通过，也不批准未登记新文档实验。

日期：2026-10-16。审查范围：`simple-output-20261016/prepare.py`、`prompts.v1.json`、`offline-preflight.json`、`registration-receipt.json`及实际`.tmp/simple-output-20261016/registration.json`。未读新留出原文/Gold，未访问密钥，未调用模型，未改冻结设计报告。

## 核验结果

独立PowerShell内嵌Python只读验证，解释器`.tmp/backend-quality-venv-20261012/Scripts/python.exe`，退出码0。实际重算结果：

- registration SHA256：`32f5cb13cbe578e89df9375a80bb347fb4e69a4f3d99b095dd5afb85d916fedc`；9个治理文件hash逐个一致，`verify_registration`通过。
- 原输入与派生输入仅`system_prompt`、`map_instruction`、`reduce_instruction`三个字段不同；work、heading structures、54单元schedule逐对象与上轮登记相同。
- 独立按runner相同requests JSON序列化重构87个实际map wire；长度/hash/顺序逐行与preflight一致，最大12456 bytes，小于固定24000。未使用仅字符数近似JSON字节。
- reduce历史map输出估计最大16724 bytes，明确`reduce_is_upper_bound=false`。这是历史文本替换提示后的估计，不能保证新map输出长度或实际token用量；线上原guard及响应后token审计保留，不为此提高预算。
- system/map/reduce共同约束必要单位、默认值、条件、例外、限定语和问题要求的Note/例子；map明确原文非穷尽限定不得省略，reduce保留原文限定。不含Gold计数、DEV题号或特殊实体规则。
- “本块无匹配证据”只用于map，且明确不得据部分块断言全源不存在；没有输出后Gold白名单删段或隐藏错项。
- 新提示由同一registration供应A/S。P0采用同轮原生生成链；核心runner未替换，现有scope重新解析校验保持。当前仅开发两源六题范围，177调用/5400秒的证明不延伸到新语料。

## 问题清单

### 🟢 Low：未使用导入

位置：`docs/review/simple-output-20261016/prepare.py:3`，`import importlib.util`未使用。

建议：未来新版本准备脚本移除。Before：`import importlib.util`；After：删除该行。该文件已绑定治理hash，本轮不为风格建议改动或重封，运行正确性不受影响。

## 优化建议汇总

1. 执行前继续使用当前登记核验，不修改已绑定提示/脚本/治理文件；真实新reduce超额时保留RESOURCE_CAP，不补跑制造成功。
2. 执行后按原Gold与终点评价全部54单元，分别核必要内容、范围外新增和实际输入支持；不因引用要求变化新增评分门槛。
3. 新文档另做曝光、家族、解析、Gold、语料可达性和完整调用图审查。当前放行仅适用于登记开发集。
