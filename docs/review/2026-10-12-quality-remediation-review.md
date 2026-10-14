# 2026-10-12 质量整改独立评审

## 审查总结

本轮最小修复方向合理：保留研究冻结失败，恢复可追溯 guard，新增真实格式/临时文件及图关系断言，未发现削弱生产覆盖分母的行为。评审结论为**有条件接受局部修改、整体交付仍阻塞**；问题统计：Critical 0、High 2（含既有交付缺口）、Medium 1（验证缺口）、Low 1（测试改进）。

审查范围来自 `docs/plans/2026-10-12-quality-remediation.md`；基线 HEAD `46b202c3e400741fd569f024412c0745f224a538`，工作树含大量其他任务修改。本评审只写本文件，不回退产品或测试。使用 requesting-code-review 的独立上下文审查组织方式；using-superpowers 明确允许已派发子代理跳过其启动流程。未请求外部模型评审，不将外部模型未调用解释为通过。

## 问题清单

### 🟠 High：后端实际安装入口未消费本轮锁与传递安全下限（既有缺口）

- 文件：`backend/pyproject.toml` 58–61、`backend/requirements.txt` 1–34、`Dockerfile.backend` 15–16、`.github/workflows/ci.yml` 103–107、160–167。
- 新增 multidict/oauthlib 安全下限在 `[tool.uv]` resolver constraints 中，手写 requirements 未携带这些限制。Docker 使用 pip -r，CI 安装及审计也使用 requirements，既不保证消费 uv.lock，也不保证消费 uv 专用 constraints；锁复扫结果不能证明实际镜像及 CI 环境版本安全。此缺口原已存在，本轮修锁后仍需明确保留，不能宣称部署整改完成。
- 建议：以同一锁构建独立验收环境，完成本地 langextract 路径与子模块 checkout 的兼容处理后，使 CI/容器消费锁定闭包。不得简单 uv export 覆盖既有手写文件而漏处理路径源。
- Before：`pip install -r requirements.txt`
- After（需先完成路径源布局验证）：`uv sync --locked --no-dev`；运行命令使用同一 `.venv`。CI 开发测试可 `uv sync --locked` 后 `uv run --no-sync pytest ...`。

### 🟠 High：供应链发现仍然存在，不能关闭安全门槛

- 文件：`frontend/pnpm-lock.yaml` 中 braces、react-router、postcss-selector-parser 条目；`backend/uv.lock` chromadb 条目。
- 独立读取本轮原始 JSON 及 exit 文件：pnpm 四条 advisory（high 1 / moderate 3），包括 braces `GHSA-vfj7-8cjw-p6xm`；后端 chromadb 1.5.9 五条原始记录、四个唯一 ID，两个 PYSEC-2026-311 记录不可算两项独立漏洞。两扫描退出均为 1。
- 这些是扫描命中，未在本评审证明实际应用全部可利用；SSR 模式等条件不能凭依赖名直接判定。Chroma 历史嵌入式例外亦不能覆盖 compose 中独立服务镜像，需保持部署路径复核与未修复事实。
- 建议：为需跨主版本修复项提供兼容迁移计划、可达性证据及明确风险决策，保留原始扫描输出与非零状态。不能忽略 advisory 或 force 升级制造通过。
- Before：扫描 exit 1 后称“漏洞整改完成”。
- After：记录剩余 advisory、适用路径、待验证迁移与 gate=BLOCKED。

### 🟡 Medium：升级运行环境与目标 Node 22 尚缺实际验证

- 文件：`frontend/.nvmrc` 1、`Dockerfile.frontend` 5–13、`.github/workflows/ci.yml` 14、`backend/uv.lock`。
- packageManager=pnpm@10.33.3、Node22、Docker frozen-lockfile 与前端单锁方向一致；旧 npm 锁已移入 `docs/archive/frontend-package-lock.pre-pnpm-2026-10-12.json`，避免继续作为默认安装入口。但本机 Node18 的 build 不能充作 Node22 镜像构建证据；旧 backend venv 的测试也不能充作 oauthlib4/PyJWT2.15.1 等升级后的兼容回归。
- 建议：独立 `.tmp` venv 消费锁，复核 installed==locked 并执行回归；运行 Node22/frozen pnpm 与容器构建。未运行前保持待验证。
- Before：旧环境测试通过 → 升级兼容已证明。
- After：分别记录旧环境行为验证和锁定新环境兼容验证。

### 🟢 Low：图摘要输出尚无行为断言

- 文件：`backend/tests/test_kg_builder_behaviors.py` 101–114。
- 序列化测试有效核对真实 JSON、节点中文及边引用，但末尾 print_kg_summary 仅调用，未来错误输出不会被发现。这不否定其前面有效业务断言。
- 建议：若该摘要是 CLI 契约，增加 capsys 断言关键计数；否则不把此调用覆盖率当该输出正确性证据。
- Before：`print_kg_summary(nodes, edges)`
- After：调用后读取 `capsys.readouterr().out`，断言对应节点数/边数及约定字段。

## 已核对的安全与范围边界

- `backend/research/isolated_guard.py` SHA256 独立读取为 `4b458d974f9ebece4251f6cd8383704473fa235d63f238b0512998b600452567`，与派发指定恢复副本一致。实现明确为 supplemental guard，依赖调用方 OS firewall、manifest/receipt/hash 与隔离启动前置验证；不能作为独立原生沙箱证明。恢复不是增加权限或修改冻结值。
- `test_supply_chain.py` 只新增排除 research 直属 test_*.py；实际 `research/test_deepseek_scope_pilot.py` 为 pytest 软件夹具，不是业务入口，既有固定 coverage 配置已排除。research 运行模块仍被扫描，AST仍遍历函数内 import，新分类测试断言这一点；本轮没有缩覆盖分母。原有 scripts 排除与未知未安装包不判缺失属于旧策略，不据此扩称供应链扫描完备。
- local_scope_v2.py 199–205 和 deepseek_scope_pilot.py 336–339 使用 stdout/stderr.write 加单换行，输出通道、JSON格式与返回码静态兼容 print；未发现错误异常内容泄露。两文件均为未跟踪文件，没有可用 Git 前版本，本评审不能独立证明完整差异只有这四处；未执行研究实验/API。
- 新 doc_processor 测试使用 python-docx/openpyxl 真格式、真实临时磁盘及异常/去重/元数据断言；KG测试覆盖窗口边界、跨页不共现、属性关系类型错误/目标缺失、多值目标与序列化，不是单纯执行无断言。未删弱原断言。
- 研究冻结 gate 应继续失败并记录漂移，不更新历史哈希来通过；本评审未批准使用旧实验为现代码证明。

## 独立执行与验证限制

本 reviewer 实际执行（仓库根；禁 dotenv、HF/transformers offline）：

```powershell
backend/.venv/Scripts/python.exe -B -m pytest backend/tests/test_kg_builder_behaviors.py backend/tests/test_doc_processor_behaviors.py backend/tests/test_supply_chain.py -q -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-quality-20261012
```

退出 0，34 passed，3 warnings，3.70s。包含 pytest-timeout 未安装导致 unknown config warning；未把 timeout 限制称为生效。测试运行的是现有 backend venv，不能证明锁升级运行兼容。

原始 audit JSON/exit 文件已独立读取，未自行在线复扫，未改扫描报告。前端 build/frozen install、guard专项及全量覆盖是协调者正在汇总的证据，本 reviewer 未自行重跑，不将自报视为独立实测。全量覆盖报告尚待完成和快照核对；无全量/API、模型或容器执行。此次允许的本地命令均执行成功，未触发额度/自动审批阻塞；外部模型/账户额度未查询，状态未知。

## 优化建议汇总

1. 先完成独立锁定环境与部署安装入口的一致性；记录剩余漏洞并阻止误称安全清零。
2. 核对最终全量测试、固定生产分母、源码快照、行/分支原始计数及非零 gate；两指标不足90%或冻结失败时禁止 commit/push。
3. 完成 Node22 容器与新后端锁环境兼容验证，再讨论交付；本轮报告不构成全项目验收。
4. 如 CLI 摘要是稳定接口，补输出行为断言。

## 定点复核追加（同日，以下状态取代首轮相应问题）

**当前问题统计：High 1 未关闭、Medium 1 未关闭；首轮部署锁消费 High 和摘要 Low 已关闭。整体仍 BLOCKED。**

### 首轮部署锁消费 High：静态整改关闭，运行兼容仍待验证

独立重读当前 `Dockerfile.backend`、`.dockerignore` 和 `.github/workflows/ci.yml`：Docker固定 uv 0.11.16，复制 langextract 到 `/langextract`、backend清单与锁到 `/app`，`../langextract` 路径源与当前布局一致；使用 `uv sync --locked --no-dev --no-install-project`，PATH指向 `/app/.venv/bin`，后续代码仍位于 `/app`。构建上下文不再整体排除langextract，同时仍排除所有子目录的 .env、.venv、缓存、output/uploads。

CI audit/test/build checkout补recursive子模块；test通过锁安装且以 `uv run --no-sync` 运行冒烟与pytest，研究测试未从全量任务中丢弃。audit export锁闭包并排除本地项目条目，使用锁定环境中的pip-audit，保留Chroma发现不ignore。build-and-push显式依赖test、dependency-audit、bandit-sast、secret-scan；test仍依赖lint。以上关闭首轮“清单重新解析而未消费锁”的具体缺陷。

这只证明静态安装路径已改正确。Docker引擎不可用与export exit0为协调者报告，本 reviewer 未执行Docker或独立export；不把静态修复充作镜像成功构建/推送或升级运行兼容证据。新 `.tmp` 锁环境尚待最终验证，首轮Medium保留。

### 首轮摘要 Low：关闭

新增 `test_summary_logs_business_counts` 通过structlog.testing.capture_logs断言唯一事件、节点/边/grounded计数和类型分布；符合实现实际日志契约。首轮用capsys的建议仅适用于stdout接口，此处采用日志捕获更合适。

### 研究夹具目录调整：接受，未缩小生产分母

独立核对 `backend/research/test_deepseek_scope_pilot.py`：只将生成的Python夹具暂存位置由研究生产目录移到既有 `backend/tests/_sandbox_tmp/research-pilot`，仍使用UUID独占路径、父目录断言和finally清理；`HERE`及adapter真实运行模块路径保持原值。动态测试代码应归入测试目录，避免coverage记录已清理夹具作为生产源码是合理分类修复；没有修改coverage排除配置，没有排除research运行模块。该调整不能替代对最终全量覆盖清单及原始计数的核验。

### 本 reviewer 新增独立验证

```powershell
backend/.venv/Scripts/python.exe -B -m pytest backend/tests/test_kg_builder_behaviors.py backend/research/test_deepseek_scope_pilot.py -q -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-quality-recheck-20261012
```

禁dotenv/HF/transformers联网环境下，退出0，48 passed、1 warning、2.93s；warning仍为现有环境缺pytest-timeout。此为既有venv上的独立定点验证，不与首次34项相加，也不证明新锁环境兼容。

独立读取 `docs/testing/2026-10-12-remediated-backend-full.log` 尾部，确为785 passed / 1 failed，失败用例为 `test_local_scope_v2.py::test_b0_preparation_is_not_execution`。没有自行重跑全量；日志尾部本身不足以证明所有输入快照或冻结失败根因，最终仍需结合完整trace和快照记录。coverage JSON曾因动态夹具源码已清理导出失败，重跑尚待最终证据；不承认旧JSON或不完整报告为双覆盖通过。剩余漏洞High、目标新环境Medium、研究冻结与覆盖门槛继续阻塞提交。
