# 三臂共同预算执行计划

用户已授权公开开发材料远程调用。范围仅复用现有公开源、隔离KG和原生/自动范围/全扫描三臂；不提交、不部署，不修改其他任务。

1. 冻结契约、输入/提示、54单元顺序、177路径证明及共同额度。独立统计设计评审关闭后实施。
2. backend/research/common_three_arm.py（执行及共同guard）和backend/tests/test_common_three_arm.py归实现者；复用现有验证transport，不覆盖旧模块。新runtime从冻结20261015代码与KG准备，加入新runner快照；逐单元新进程、新rewritecache。离线验证真实SDK与requests捕获、预算边界、超限/UNKNOWN停机、完整schedule/Gold隔离及源码/KG验证。
3. 独立代码审查；正式运行根.tmp/common-three-arm-final-20261015，最终源码、输入及依赖身份写入registration.json并封存hash，执行后归档到docs/review/common-three-arm-20261015（源码保存txt快照）。只在无阻断时远程执行；安全记录原始成功请求/响应及使用量，不保存headers/原始异常。
4. 冻结全部输出；生成匿名包，两独立内容评审锁表，第三人处理分歧；另行实际输入链证据审计。范围、条目、证据分别报告，不混合得分，不夸大N=2。
5. 复核收据/评分/归档hash，更新研究memory。失败保留明确状态和费用，不改预算补跑。无commit/push。

验证边界：专项真实协议transport离线行为测试和实际公开源API回执。研究脚本不是新增生产API，无需伪称整站验收/双覆盖率/人工Gold认证。
