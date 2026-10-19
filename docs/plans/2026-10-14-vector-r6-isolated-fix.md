# R6 隔离兼容与异常日志修复计划

沿用用户已确认的向量库替换设计/MVP；本轮修复R5发现的两个具体缺口，不授权生产集成、原数据迁移或发布。使用subagent-driven-development、TDD及独立评审。旧冻结目录只读；根工作区其他后端改动保留，不复制为已验证事实。

## 目标及文件所有权

- debugger：`.tmp/vector-r6-debug-20261014/`、`docs/review/2026-10-14-vector-r6-debug.md`，核实宽record整数的真实输入转换与原生源码；NaN仅观察，不擅自更改产品策略。
- coder：新`.tmp/vector-r6-20261014/`、`docs/testing/vector-r6-20261014/`及`docs/testing/2026-10-14-vector-r6.md`，从R5清单核hash复制，不修改旧冻结。
- reviewer：独立`.tmp/vector-r6-review-20261014/`、`docs/review/2026-10-14-vector-r6-review.md`；先审局部契约，再审最终代码与独立新输入。
- root：计划、局部合同、复验收据与memory；不修改生产代码/主锁/环境密钥。

## 实施与验收

1. 核R5的284冻结文件及锁环境。保存当前生产消费者源码hash；若消费者变化，先核实际变更和测试绑定，不将旧AST执行误称当前全链验收。
2. debugger确定宽Python int记录是否经通用PyO3 signed-i64失败后f64提取，区分直接binary64值与持久化JSON重解析；验证正负端点、超u64、巨大整数、signed zero及where比较，不只匹配三条已知值。无机制证据不猜修。
3. 独立reviewer审局部合同。coder先保存有效红测试，然后只在新副本实现已核机制。保留原payload与compat读回、按原生存储类型投影；不查表、不丢字段、不缩过滤支持域。
4. 日志候选保持Exception.__cause__/__context__和原traceback对象；在format_exc_info之前将typed VectorStoreError的日志转换为固定错误分类与结构化帧。仅输出静态类型/固定code/operation及经验证的帧标识与行号；禁止message/repr/locals/源码行/任意附带error字符串进入候选输出。普通日志沿用原策略；不得宣称其任意值都安全。
5. 用真实消费者函数与真实logging处理链的隔离副本，验证裸合成标记、多层cause/context、循环/长链、恶意__str__，同时保留错误分类、failed遥测、原因链类别与栈帧。输出文件和console均验证；故障注入与真实原生I/O故障分开记录。
6. 真实锁定Chroma与Lance离线差分，分别记录有效红/绿命令、退出码、原始结果、依赖与输入hash。复跑受影响旧76/44/162/9cosine/312+84/144+32/fresh128及R5门面/异常测试，不改旧输入或断言。
7. 冻结最终副本，独立reviewer新seed/新输入及静态审，root复验后回流合同/设计/memory。没有独立验证的项目不标关闭。无产品变化不冒称新跑产品双90；有当前其他任务源码漂移如实单列，不沿用旧报告宣称当前全树通过。

## 仍开放的出口

2026-10-15执行出口：1—7已按所测隔离范围交付。最终186冻结文件、作者15命令exit0、root复制四命令exit0，独立新32记录/90where及攻击日志五命令exit0，详见R6合同最终节。有效旧断言/typed子类红、中间fixture构造失败均保留。当前产品双90未重跑且有他人源码漂移，未提交或部署。本轮附带原生审计发现Lance新安全阻断，已回流总体设计，仅重开受影响选型安全，不回退已测R6正确性证据。

用户已明确NaN及±Infinity查询向量在执行前返回invalid_input，正式策略决定完成，实际测试仍须绑定最终代码。formatter任意binary64依据、native安全、完整CRUD/分页/快照/并发恢复、完整worker/API消费者及迁移仍各自验收。R6通过只能关闭其已测隔离缺口，不能清零现役Chroma四公告。新核心组件正式集成计划需在全部门槛证据齐全后提交具体设计供用户确认。
