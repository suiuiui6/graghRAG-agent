# 隔离向量过滤数值语义修复计划

用户授权：明确超界数值转换语义，修复并复验。范围仅隔离原型，不是生产替换、数据迁移或系统运行库升级。

1. debugger在独占临时目录用锁定Chroma1.5.9和显式合成向量测真值：int64端点、相邻float、正负fraction、有限极大值、六比较和in/nin；分别记录成功ID及错误类别。用可区分截断/饱和/普通数学比较的输入，输出版本绑定语义合同和冻结原始证据。
2. 独立reviewer先核合同与真实真值，阻断意见关闭后才修改。不能以不同语言的常识转换或浮点容差替代metadata语义。
3. coder仅在新r3副本修通用numeric编译分支，不覆盖r2/阶段1冻结。先红后绿；Python int仍精确保留，不将所有数值转float、不按具体夹具值特判。合法范围与错误边界单独说明。
4. 最终复验原76、原44（包括原4失败）、新增语义矩阵、9组cosine过滤后top-k与评分、拒绝边界/持久化恢复；独立reviewer复制最终输入到独占目录复跑。记录最终脚本、夹具、锁、命令、exit和前后hash。
5. 回流设计与memory。关闭此项局部H1不等于全部where兼容、生产替换或Chroma漏洞清零；完整adapter、增量schema、全局快照/并发崩溃、native安全与迁移保持原状态。

文件所有权：debugger持有numeric-semantics独占tmp、contract及对应testing证据；reviewer持有numeric-review独占tmp和review报告；coder待真值审查通过后持有新r3独占tmp及报告；根仅回流计划/设计/memory，保留其他任务所有修改。Windows异步导入需正规沙箱外审批离线执行，不读取.env或调用模型。
