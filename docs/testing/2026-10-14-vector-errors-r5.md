# R5 公共异常边界隔离验证

状态：候选实现及作者验证完成，[独立复核](../review/2026-10-14-vector-errors-r5-review.md) 条件通过，未发现本轮新增阻断；非完整 adapter，生产替换仍 BLOCKED。未改生产、主锁、.env、原数据或旧冻结；未提交、推送、部署。

## 实现与范围

从 R4b 110 文件冻结核 SHA256 新复制，原件未变。stdlib `vector_errors.py` 定义固定 code/operation/retryable/message，输入与能力错误兼容 ValueError，均不继承 TypeError；storage 不继承 ValueError/TypeError。cause 保留。generic_filter 显式输入 raise 类型化异常，只有纯 numeric parser/json 调用窄转输入错误；Arrow/native 表达式及其余 Exception 转 storage，BaseException 透传。混合 metadata key 在 sorted 前拒绝。Length mismatch 安全短语保留。

最小 ProbeStore 仅实现 open、encode、search、read、count、scan。read/scan 每次最多 10000 条，非全量且未实现分页。增删改、现役 VectorStore API、全量分页/快照、并发写入、恢复及迁移均 NOT_IMPLEMENTED。本轮不声称完整 adapter。record signed-I64、宽 query/parser、集合首类型与 raw/compat 保持 R4b。

## 实际验证

命令与退出码见 [执行收据](vector-errors-r5-20261014/r5-execution-receipt.json)，最终源码与输入见 [冻结清单](vector-errors-r5-20261014/r5-freeze-manifest.json)，依赖身份见 [环境](vector-errors-r5-20261014/r5-environment.json)。所有真实依赖运行均正规 require_escalated 离线执行，两个禁用环境变量启用；无供应商/模型/.env。runtime 原17锁定包，新独立 testenv 增加 structlog 26.1.0，不跨环境 sys.path。独立环境的 [11 文件冻结](vector-errors-testenv-20261014/manifest.json) 由 root 保存：18 锁与安装漂移 0，原17 runtime同版本；官方 PyPI audit 18 项零公告，native安全 NOT_COVERED。早期缺 structlog 的失败与中间试跑不作最终证据，最终独立 testenv 复验为准。

- 修复前红：非法集合裸 ValueError、混合键裸 TypeError、record 溢出裸 ValueError，3 项缺 code，exit 1；[红日志](vector-errors-r5-20261014/r5-red.log)。
- 新门面红 2 项 exit 1（score 同向1/正交0/反向-1，超大整数向量裸 OverflowError）；修复为 `round(1-distance/2,4)` 及显式向量校验窄转 invalid_input 后，真实 facade 同向1/正交0.5/反向0、prefilter top1、超大整数拒绝 2 个测试绿 exit 0。原9 cosine只覆盖旧projection消费路径，此新增测试实际经过新门面。
- 最终 5 个 unittest 分组 exit 0：合法/无匹配、过滤非法/解析溢出/维度/非有限/批长/记录、真实普通文件作为 DB 路径拒绝、native col 和 backend ValueError/TypeError/OSError 注入、read/count/scan 故障、KeyboardInterrupt/SystemExit 透传。输入过滤拒绝断言 table.search 未执行；storage cause 类型保留、公共 str/dict 无裸合成标记。
- 原专项 76、44、162、9 cosine、312+84、144 宽整数+旧32、fresh128 全部 exit 0；旧行为断言未弱化。旧双90产品测试不在本轮重跑。root 私有复制最终候选后的 5+2 测试均实际 exit 0，见 [root 复验收据](vector-errors-r5-rootverify-20261014/manifest.json)。
- 真实 Chroma 15 项原生观察 exit 0：成功、无匹配、过滤错误、query U64/数值溢出、维度、批长、记录错误、真实坏路径；供应商原生类与消息保留，不冒称等同应用类。

## 消费者与日志

执行真实 retrieval.py 的 `_search_vector_store_with_projection`、`_vector_recall`、`multi_path_recall` AST 函数 subset，真实 source_control/evidence_trace 函数、真实合成 Lance store；源 hash 见 [消费者收据](vector-errors-r5-20261014/consumer-receipt.json)。合法命中 executed/count1、真实无匹配 executed/count0、storage 失败 failed/countNone；ValueError/TypeError backend 注入各 search 仅一次，不触发旧签名重试。并非完整 module/API/worker 执行。

真实 logging_config.setup_logging 处理链捕获实际 consumer warning：API-key 样式值被 [REDACTED]，裸 synthetic marker 仍在 cause traceback。公共 str/dict 安全单独通过；最终日志任意值脱敏仍 OPEN。日志 [consumer-final.log](vector-errors-r5-20261014/consumer-final.log)。未删除 cause 或伪称日志完全安全。

## 明确兼容缺口与未执行

Chroma metadata 2**63、2**64、-2**63-1 均原生接受，get 读回 float；hex 为 0x1p+63、0x1p+64、-0x1p+63。候选当前 I64 记录域拒绝，明确 compatibility GAP。Chroma query_embeddings=[[NaN,0,0]] 也接受，候选非有限向量拒绝，同属显式差异。详见 [原始观察](vector-errors-r5-20261014/chroma-errors.json)；这些新事实不得用标签归一化声称等价。

完整 worker/API/provider 全链 NOT_RUN。formatter 任意 binary64 等价、原生安全、完整生命周期/并发恢复/迁移仍未证明；仍禁止生产选型/迁移。项目提交覆盖/扫描门槛未在本轮重新验收，无 Git 提交。独立 reviewer 已对最终284文件候选核hash并执行新输入，评分、超大int、native compile/schema及真实消费者故障边界通过。本轮实现无新增阻断；保持最终候选SHA256 `43D38E03549F64762734D1D0339C7C87C3C4361346B1CB390983C3B293269D4C` 不变，候选清单历史 PENDING 字段由此后独立评审结论补充，不追改冻结。




