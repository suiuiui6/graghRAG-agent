# H2 数值入口兼容定位及隔离修复

用户授权尝试解决H2，沿用项目工作流，不启用goal/Harness。只读现役依赖实现与官方锁定版本源码，写入独占隔离探针/新r4候选；不修改生产、主锁、原向量库、Gold或旧冻结。

1. debugger定位首次数值变化：Python raw值、wrapper传参、RustBindings解析、存储/readback及query literal分别留原始收据。核JSON/serde及数值类型上下界，不先认定f32或查表归一化。
2. 独立reviewer确认版本绑定入口合同和可实施的泛化方案；必须明确已知数值域/错误行为及未验证项。
3. 可实施时coder在新r4副本先红后绿修兼容层，原payload与派生比较表示分开。不得调用旧Chroma作为候选实现、按案例特判、以舍弃原失败或无依据改变类型制造通过。若需新运行依赖，先独立锁和最小真实I/O、安全评估，不污染现役环境。
4. 复验完整312原始矩阵及84边界、新的独立输入、r3原76/44/162及9cosine消费者；错误行为与成功ID分别判断。独立复制最终冻结输入复跑，保存所有红绿和hash。
5. 回流合同/设计/memory。H2局部关闭也不自动批准生产替换、迁移、native安全或全链验收；机制无法可靠重现则如实记录具体阻塞。

所有权：ingress_root_cause持有debug tmp、语义contract及debug证据；ingress_review持有review tmp及报告；coder待合同确认后独占r4；根只回流计划/设计/memory。Windows真实异步依赖按正常审批离线运行，不绕过沙箱限制，不读取.env或访问模型。
