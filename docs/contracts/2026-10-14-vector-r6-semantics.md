# R6局部兼容与日志契约

状态（2026-10-15）：R6已测隔离缺口通过作者/root复验及独立最终评审；生产替换仍因原生安全等门槛阻断。继承R5应用异常合同及已确认替换MVP范围，不改变生产行为。

宽整数记录以真实锁定Chroma1.5.9转换机制为准：必须核原生源码和合成oracle，再决定投影类型及兼容读回。超I64不再无依据等同非法输入；超出binary64可转换域的处理须实测并显式区分能力/输入错误。数值不得夹具特判或浮点容差掩盖bit差异。NaN查询接受与有限向量策略是显式产品取舍，未决定前保留GAP，不自动扩大数据支持承诺。

用户随后明确确认：替换库拒绝NaN及正负Infinity查询向量，返回可识别invalid_input，存储查询不得执行。这是正式记录的有意兼容性变化，不再要求复制Chroma接受但返回NaN距离的行为。仍须验证所有非有限位置/容器与合法有限输入的回归；此决定不自动关闭其他兼容性缺口。

typed VectorStoreError原对象、cause/context及traceback在内部保留。候选日志在异常格式化前转换为结构化安全诊断：固定应用code/operation、静态异常类别、可定位栈帧与行号、链关系和截断标记。不会调用异常str/repr，不记录异常参数、locals、源码行或未审核附带字段。保留traceback定位不等于输出原始异常message。

帧路径、函数名、异常类型名称也须考虑动态来源，不能只移除message就宣称任意标记安全；独立评审确定稳定安全标识/白名单，未核来源的标识须替代为固定标识。链遍历须有循环检测与预算，输出安全不得递归执行用户代码。普通非向量异常日志不在本契约的任意值保障范围。

独立设计复核约束：帧映射使用已审核实际加载函数的code对象身份到固定标识，不以动态filename/function字符串白名单代替；未注册帧为固定unknown、行号仅接受内建整数。异常类别以exact class identity映射，未知子类为固定Exception。typed事件整体重建固定event ID/安全分类/明确验证的scalar遥测白名单，不能继续携带event/logger/contextvars或任意extras。原因链即使由外层普通wrapper包含typed error也走安全路径；直接通过BaseException原生descriptor读取cause/context/traceback，避免恶意__getattribute__/str/repr；遍历预算及循环输出固定标记，原异常引用保持不变。测试须覆盖伪造代码名、动态异常类名、所有事件字段携标记的情况。

测试必须经过实际消费者及实际logging链的隔离副本，console/file同时断言；正常成功和空命中遥测保持，故障只查询一次、failed/count=None。该执行若为AST subset或故障注入必须明示，不冒充完整API/worker真实故障验收。

2026-10-15独立实现复核补充：安全路径必须覆盖VectorStoreError的未知子类，识别继承关系须读取真实type的原生MRO descriptor并按基类身份比较；诊断类别仍采用exact class静态映射，未知子类为Exception。root与reviewer均已保存当前实现遗漏子类的有效红，最终须复验关闭。

异常链预算耗尽且仍有未知尾部时，为避免typed异常藏于超长链而泄露，候选日志保守重建安全事件、code/operation为unknown并带truncated标记。即使最终尾部不含typed，此长链事件也会丢弃原始任意字段；这是明确的诊断降级，不宣称所有普通事件原样保留。预算内确认无typed且未耗尽的普通异常仍沿用既有策略，不提供任意值安全保障。

有界诊断的节点按首次遇见关系摘要记录，不包含完整parent拓扑；seen身份重复仅证明环或共享引用，使用cycle_or_shared标记，不误称精确环检测。原因对象及上下文仍原样在内部保留，必要内部诊断可使用原对象，不向公共日志输出原始内容。

## 最终有界验证与剩余门槛

[R6证据](../testing/2026-10-14-vector-r6.md)绑定186文件冻结SHA256 `37a4ca29ce343e1621235b1bb8fdbee52beb120b67134fc3b32d1e6c1d1fbac5`。最终作者15命令exit0；root核186文件并私有复制后亲跑R6三项、异常五项、门面两项及48记录/126过滤真实差分，四命令exit0，见[root收据](../testing/vector-r6-rootverify-20261015/root-receipt.json)。[独立审查](../review/2026-10-14-vector-r6-review.md)核38执行输入及前后漂移0，独立32记录/90过滤位级差分0、实际消费者AST三函数与console/file安全日志通过，五命令exit0，[独立收据](../testing/vector-r6-review-20261015/execution-receipt.json)。未知typed子类遗漏的有效红已补绿关闭；原cause保留，任意值保障仅限本候选安全路径。

宽record转换在已测有限域关闭；超binary64整数拒绝/原payload保真/派生float类型与读回bits均有新输入证明。NaN/±Inf查询拒绝策略及执行前错误已验证。上述不是formatter任意binary64等价证明或完整adapter/worker/API验收。

[新增原生审计](../review/2026-10-14-vector-native-security-review.md)得到LanceDB SBOM20条/18唯一漏洞匹配，该实际Windows PE不完整静态恢复匹配9条（不与SBOM记录相加）；尚未证明函数可达/可利用，也不能按禁云配置直接排除。候选仍BLOCKED，不能以R6正确性通过替代安全准入。原Chroma四项公告保持未修；完整生命周期、可信构建/运行库、当前产品双90和生产集成另验。
