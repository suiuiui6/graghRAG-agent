# 开发模型迁移、结构与预算守卫独立复核

2026-10-15；独立只读源码与离线行为审查。未读取 `.env`、Gold/answers，未联网、调用模型或操作生产索引。主任务仍有其他修改者，以下问题绑定本次读取快照，修复后需定点复核。

## 审查总结

初审发现 0 Critical、2 High（R1/R2），旧模型迁移 F1/F2 已关闭。**最终定点复核 R1/R2 均关闭，未关闭问题 0**，详见[执行复核](2026-10-15-development-execution-review.md)。下文保留初审复现与当时快照；不把初审绿测试当作缺陷关闭依据。

## 问题清单

### 🟠 High R1：缺字体证据的后续数字标题被静默跳过

- 位置：`backend/research/development_structure.py:153–160`。
- 问题：数字标题缺 font 时直接 `continue`，没有 diagnostics。陌生 PDF 的 `1. First` 有 Bold，而 `2. Second` 的 font 不存在时，选择“第1节”返回 RESOLVED，范围包含第2节正文。契约要求缺字体证据弃权；不能以现有两份源结果正常替代边界验证。
- 建议：对可疑数字标题缺字体证据生成不确定边界诊断，由现有 resolver 弃权；保留正常字体普通编号列表不提升为标题的行为。
- Before：`if not bold or not font or not numbered: continue`。
- After（示意）：先识别数字候选；`if numbered and not font: diagnostics.append(...); continue`，再执行有字体证据的标题规则。
- 独立离线复现：诊断 `[]`、结果 RESOLVED，文本包含 `2. Second\nexcluded`。未发任何 HTTP。

### 🟠 High R2：损坏 choices 的响应绕过首失败关闭

- 位置：`backend/research/development_budget.py:163–174`。
- 问题：`choices=[None]` 时 `c.get` 抛 AttributeError；异常发生在 transport try/except 外，记录仍 SENT_PENDING，`closed=False`，同一进程第二次 `_begin` 仍允许。顶层非对象 JSON 也存在 `.get` 类型异常。重启时 pending 拒绝恢复不足以保证当前原生调用捕获异常后的重试关闭。
- 建议：先验证顶层对象和每个 choice/message 类型，所有不合契约结构统一保存 FAILED_CLOSED 并抛安全 BudgetStopped。
- Before：`finish = [c.get('finish_reason') for c in choices]`。
- After（示意）：`valid_choices = isinstance(choices, list) and bool(choices) and all(isinstance(c, dict) for c in choices)`；无效进入统一关闭分支。
- 独立离线复现：`AttributeError closed=False record=SENT_PENDING`，后续第二次 reservation 被接受。使用假 key 和临时目录，无实际 transport。

## 旧问题关闭及验证

1. F1：worker/pipeline 原生 ModelConfig 已调用 `non_thinking_provider_options`，flash/v4 返回 `reasoning_effort='none'`；其他显式模型不附该字段。新增六种模块/模型组合通过真实 LangExtract provider → OpenAI SDK → httpx.MockTransport 实际序列化断言。没有把假工厂 AST 断言当作 wire 证明。
2. F2：generator 模块注释已描述 flash/v4 显式非思考行为。
3. `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -`，设置 PYTHONPATH=backend、socket.connect/create_connection 拒绝外连，执行模型、development_structure、development_scope、scope_v2 四个测试文件，`-q -p no:cacheprovider --basetemp .tmp/resume-review-20261015b`：**76 passed in 7.20s，exit 0**。不是产品全量或旧 157 专项复跑。
4. 独立脚本只读 sources.json、canonical、原件、block/page map、已保存 Poppler XML、questions.input.json，重新计算来源 SHA、结构与六题范围，和已有 sidecar/actual-nongold.json 比对：**2 source identities + 2 sidecars + 6 non-Gold range results MATCH，exit 0**。未读取标准答案或按题号路由；规则源码无六题 source_id/题号/目标范围特判。
5. HTML 原生 h1–h6 与 table 祖先绑定、pre 注释不提升、Unicode半开坐标与字节组装边界符合本轮检查。PDF使用字体/原节点顺序与页内唯一完整行匹配；R1仍阻断其缺证据情况。

## 已读快照 SHA256

```text
development_structure.py 912D059495B7AF9B7CA5BEABC3350B8D2232C8044189FE61AC75EBB6985DF599
development_scope.py 987DA1F223DC3EC9D4D0021F55395BD4858BFF83B3BD874670D6820454B525F2
config.py 389B9D7A978ABBC2DD68CA5CB405C4FD7C8ED6BB6DF5890ED71A0DFB93079FEE
worker.py 8748F821FC49DD1621BC04EAE83A89F0E3A451DBD14D5E11EC895025D2E5A4F3
pipeline.py 6F20E4DAC769FAB1EE2E85EF19E8E9A4845FC028934FF4C9ADFDB1E93FB3A115
generator.py 55D8612E9D17E8A796BA4A9E0E295A34F14578CE46705CA70E2904DEA1C6679E
test_generation_model_selection.py 556B63B04BBDE04FA9D0C2BC2F39570FC113002D3B1FF9CA60AB0A5A6E3C37F5
```

## 优化建议汇总

最终复核：R1缺字体、XML页缺失/重复及bold数字分片无法组成完整标题均保守诊断/拒绝；正式候选环境范围新旧四文件82 passed/5.98s，2来源/2sidecars/6非Gold结果重新计算MATCH。R2对损坏JSON/choices/message/content统一FAILED_CLOSED；实际SDK httpx2 transport已纳入guard，guard/isolation29 passed/6.04s。最终structure SHA951db304b00918b13719fb8f9383d8aa9edef17d1f2994f4575bd339c81aa004；其余最终执行模块见执行复核报告。仅已授权公共开发有界资源测定可进入执行，不能据此证明方法缺口。

1. 先关闭 R1/R2，复跑陌生文档和损坏 wire 回归；现有绿测试不覆盖两次独立复现。
2. 隔离 runner 的实际 SDK 可能使用 httpx2；transport guard/预检必须覆盖实际 SDK 类，并以底层 MockTransport 证明零网。该主审已发现事项正在修，本报告尚未判关闭。
3. 仅在正式候选环境实际预检通过、修订前置额度登记且快照一致后运行预算；索引、查询与输出上限分别记录，不中途抬额度。未提供产品全量、覆盖率、安全扫描、提交或部署准入。
