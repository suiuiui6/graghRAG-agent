# 三臂共同预算实际收据：独立资源与输入链复核

结论：**资源与实际输入链核查通过**。本报告不评价答案正确性、范围科学判定或方法优劣，不读取Gold或内容评审结果，不推进M2。

正式登记SHA256 `0bc8fe290a67d3b3c047372e2685eb33cd5fed7c681ddd95da76df40233228ec`；执行器SHA256 `d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e`。独立脚本读取全部54个原始ledger、54个result及父进程状态，逐请求解析wire并复算，未仅依赖root摘要。

| 臂 | 单元 | HTTP尝试 | 输入tokens | 输出tokens | 总tokens | 请求JSON UTF8字节 | 输入缓存命中tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0原生scoped KG | 18 | 36 | 19971 | 4147 | 24118 | 96956 | 11520 |
| A自动范围 | 18 | 42 | 56176 | 19932 | 76108 | 250405 | 38504 |
| S全源扫描 | 18 | 81 | 176076 | 37248 | 213324 | 775456 | 103804 |
| 合计 | 54 | 159 | 252223 | 61327 | 313550 | 1122817 | 153828 |

54单元均COMPLETED，159请求均HTTP200、finish_reason=stop、费用token账本KNOWN；无未知成本请求。本地父进程记录743.4261128902435秒。所有请求实际为deepseek-flash、temperature0、thinking disabled、非流式；18个P0各一次300输出声明的预处理及一次2048回答声明，无回答重试。A/S声明2048。回执159个不同ID，model均deepseek-flash、fingerprint均`aeb56401ca74e127821c4f9126dcb669`；仍不能据同fingerprint证明固定权重。

全部单调用/单元额度逐条检查通过：最大请求wire16220字节（上限24000），最大单元74233字节（192000）；最大单调用input3006/output1527；最大单元input14329/output3399；最大单元27.625585079193115秒。159尝试低于177路径上限。实际tokens不是金额、发票或供应商最终结算；供应商缓存命中未被强制消除，时间/账本不构成禁缓存的公平成本因果比较。

## 实际输入链

- 87次map逐次核完整system/user messages，问题、heading index、chunk坐标及源切片全部精确相等，不只匹配记录的坐标。18个S单元的规范文本全源连续切片覆盖成立；18个A单元使用登记selected spans，六题resolver在当前最终冻结模块下重新离线执行一致。
- 36次reduce精确核完整messages，等于登记reduce指令/问题及该单元全部map原始输出、chunk ID和call ID的有序数组；最终A/S答案等于最后provider输出。此证明只涉及信息进入模型的链条，不证明map或reduce语义无损。
- 18个P0核最终wire messages等于原生evidence trace的serialized_model_context，raw_model_answer等于实际provider原始输出，原生后处理答案截前4000字符后等于API答案；实际effective_config为KG-only，multi-query/global/cross-encoder均false。该路径为ASGI函数调用与管理员fixture，未声称JWT/HTTP网络端到端通过。

## 资产与保密边界

正式`verify_registration`核验在独立审计前后均通过：146源码、5个KG/store、登记规范文本、snapshot、治理文件、永久KG归档及7项依赖身份匹配；本次不代签生产3306文件的全库扫描，生产资产盘点由root的独立证据负责。

独立核查所有保存的请求/响应对象不存在authorization/api_key/access_token/refresh_token/headers字段，且wire SHA和完整JSON与结构化收据一致。核查者未读真实key，不能凭结构检查保证正文没有实际密钥；真实key匹配scan由root另行核实。本轮也未新增网络或模型调用。

## 可复现记录与限制

实际命令：`.tmp/backend-quality-venv-20261012/Scripts/python.exe -B .tmp/common-three-arm-final-20261015/independent-resource/audit.py.txt`；exit0。独立脚本SHA256 `fc002748ed5066a33c36722f43665dbe1b0a113debee67144519d2877eeb62fc`。脚本、机器结果及完整专家合同分别位于正式profile的`independent-resource/audit.py.txt`、`audit.json`、`result.yaml`；audit.json绑定全部108个原始result/ledger文件hash。

本报告仅资源/输入链PASS。两来源、六题、三次重复存在依赖，不将159调用或54答案当独立文档样本；未作语义评分、显著性、功效、泛化或创新判断，未改变M2_OPEN。

下一步：编排者汇合本资源核查、单独真实key扫描及独立内容/证据裁决，再形成限定开发结论。
