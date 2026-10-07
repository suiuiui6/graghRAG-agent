# 日志与异常治理（F003+F004）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 backend 的日志从"print + 无关联 ID + 泄露凭据"变为"structlog 统一出口 + request_id/task_id 关联 + 全链路脱敏"，异常从"229 处宽捕 + 134 处静默吞 + 零错误码"变为"分层错误码 + 显式失败语义 + 静态门禁防回流"。

**Architecture:** 新建**顶层 stdlib-only** 的 `backend/errors.py` 承载 `ErrorCode` 二维枚举（阶段×失败类）+ `PipelineError` 分层异常 + 单一 `classify_external_error` 映射入口；与 FastAPI 相关的 `register_exception_handlers` 在**函数体内**惰性 import `fastapi`/`models`，因此 `errors.py` 可被 `worker.py` 的同步线程池路径与 CLI 脚本安全复用。`routes/ingest.py` 的 `TaskError.code` 从字面量 `"PIPELINE_ERROR"` 升级为枚举值（`TaskError.code` 是 free-form `str`，无需数据迁移）。`logging_config.py` 补齐三个缺失件：`task_id` 上下文绑定、脱敏处理器、`format_exc_info`。`server.py` 注册首个结构化异常边界（`ErrorResponse` 从死代码转为实际契约，`error`+`detail` 双写过渡）。`worker.py` 的 `return None` / `(0,0)` 失败语义收敛为 raise + `ExtractionOutcome`。最后用 ruff + bandit 把规则固化进 CI。

**Tech Stack:** Python 3.12、FastAPI、structlog、pydantic v2、ruff、bandit、pytest、GitHub Actions

---

## 背景事实（已侦察确认，勿再猜测）

| 事实 | 证据 |
|------|------|
| 非测试 `print()` 共 **137** 处，其中 **109** 在不可 import 的 CLI 脚本 | 36 `pipeline.py` / 34 `run_evaluation.py` / 24 `agentic_rag_mvp.py` / 11 `build_indices.py` / 4 `scripts/check_imports.py`；均含 `if __name__ == "__main__"`，全仓零处 `import pipeline` / `import agentic_rag_mvp` |
| 需改造的库代码 `print()` 共 **28** 处 | 19 `kg_builder.py` / 4 `worker.py` / 2 `oss_uploader.py` / 2 `embedding.py` / 1 `doc_processor.py` |
| 另有 `traceback.print_exc()` **3** 处（也是 print 违规） | `worker.py:753, 778, 790`；`routes/ingest.py:121` 另有一处 `traceback.print_exc()` |
| `except Exception` 共 **229** 处，裸 `except:` **1** 处 | 裸 except 唯一位置 `routes/query.py:277` |
| 静默吞（`pass`/`continue`/`return None`）约 **134** 处 | 其中 `services/catalog.py` 15 处中 13 处为 `pass` |
| `worker.py:870` 的 Ollama `except Exception: continue` 是**正确性 bug**，非风格问题 | 批次失败被跳过，`worker.py:899` 返回 `(0,0)`，调用方 `worker.py:786` 无法区分"文档确实无实体"与"Ollama 挂了" |
| `logging_config.py` **无** `task_id` 绑定机制 | 仅有 `request_id_var`（`logging_config.py:19`）与 `set_request_id()`（`:103`） |
| `logging_config.py` **无**脱敏处理器 | `structlog.configure`（`:83-95`）= `merge_contextvars / add_log_level / add_logger_name / TimeStamper / JSONRenderer` |
| **traceback 被静默丢弃** | 实测 `logger.error(..., exc_info=True)` 输出 `{"exc_info": true, ...}`，**无堆栈** —— 链中缺 `format_exc_info`。全仓 6 处真实调用（`conversation.py:420,446` / `retrieval.py:331,383,533` / `server.py:327`）全部受影响 |
| **实测零脱敏** | `logger.error(..., api_key='sk-FAKE_TEST_PLACEHOLDER_000000000000')` 原样落盘 |
| `server.py:266` 泄露**活的** bearer 凭据 | `logger.info("server_started", file_access_token=FILE_ACCESS_TOKEN)`；该 token 由 `security.py:7` 生成、`security.py:26` 比对、`routes/documents.py:132` 用于文件访问鉴权 |
| 泄露值实际落盘 **126 次**，分布在 **9 个轮转文件**里 | 修正：初版写"3 次"是错的 —— `head -5` 只看 `app.log` 一个文件，把截断当成了全量。实测 `output/logs/app.log` 本身含 **0** 处，全部证据在 `app.log.2026-0{6,7}-*` 轮转文件中（06-14 最多 44 处，07-04 有 22 处）。**清理脚本必须 `rglob("*.log*")` 覆盖轮转文件**，只处理 `app.log` 会假成功 |
| **无任何活密钥进入日志** | `output/logs/` 中 `sk-` / `LTAI5t7...` / OSS secret / MinerU JWT 均 0 命中 |
| `output/logs/` **已被 gitignore 且未跟踪** | `git check-ignore -v` → `backend/.gitignore:11:output/`；`git ls-files output/logs/` 空 → **无需 git 历史清理** |
| 全仓**零** `@app.exception_handler` | FastAPI 默认 500 生效 |
| `models.py:182 ErrorResponse` 是**死代码** | 无任何代码返回它；所有路由用 `HTTPException(detail=str(e))` |
| `PIPELINE_ERROR` 字面量仅 **1** 处，前端无引用 | `routes/ingest.py:71`；`frontend/src/lib/types.ts` 无匹配 |
| `PIPELINE_ERROR` **不是**枚举成员（将失效） | 需在 Task 8 替换 |
| `models.py:125 TaskError.code` 是 **free-form `str`** | 不是 enum → 已落盘的旧任务记录仍可反序列化，**无需数据迁移** |
| 仅 1 个自定义异常类 | `retrieval.py:43` `CrossEncoderUnavailableError(RuntimeError)` |
| 5 个模块仍用 stdlib `logging.getLogger` | `retrieval.py:34` / `worker.py:27` / `routes/health.py:8` / `routes/rag_query.py:26` / `routes/graph.py:7` —— 它们**绕过**脱敏链 |
| 19 个模块已用 structlog | `from logging_config import get_logger` |
| MinerU 错误走 **HTTP 200 + body `code != 0`** | `worker.py:963`；纯 `isinstance` 分派会漏判鉴权失败 |
| MinerU 客户端已有部分正确形态 | `worker.py:967/989/1006` 已分离 `except subprocess.TimeoutExpired` |
| `bandit>=1.7.9` 已在 dev 依赖并锁定，但**从未被调用** | `pyproject.toml:53`；CI 无 bandit 步骤 |
| ruff **未**在 `.venv`，CI 用**未钉版本**的 action | `chartboost/ruff-action@v1`（`.github/workflows/ci.yml:22-25`）；`.venv/Scripts/` 无 ruff |
| `pyproject.toml` 目前仅有 `[tool.uv.sources]` + `[tool.pytest.ini_options]` | 无 `[tool.ruff]` |
| `pytest-timeout` 未安装在 `.venv` | 实测 `pytest --timeout=120` → `unrecognized arguments`（`pyproject.toml:62` 声明了 `timeout=60` 但依赖未装） |
| 已有 2 个测试 stub 掉 structlog | `tests/test_community_global_mode.py:15-38`、`tests/test_kg_indexed_recall.py` 把 `format_exc_info` 置为 no-op —— 说明该缺失已被绕过而非修复 |
| FastAPI 中间件顺序：`add_middleware` 后被 `app.middleware` 包装，**最后定义的最先执行** | `server.py:294` CORS → `:303` auth → `:306` jwt → `:310` tenant → `:314` request_id → `:336` rate_limit（实际最先执行） |

| 基线测试状态：**5 failed, 276 passed** | 实测 `pytest tests/ -q`（50.4s）。5 个失败**全部**在 `tests/test_phase2.py`，且都是数据依赖断言（`test_build_catalog: assert 0 >= 3`、`test_export_kg_json: assert 0 >= 3`、`test_compute_quality: grounding_rate == 0.0`、`test_search_entities`、`test_list_entities_by_type`）—— 依赖 `output/kg/` 下存在真实 KG 产物，与本次改造无关 |

> **回归判定基准**：改造前已有 **5 个失败**。各任务 Step「确认无回归」的标准是**失败的仍是这同样的 5 个**，不是「全绿」。不要试图顺手修这 5 个 —— 它们需要真实 KG 数据，属独立任务。测试总数会随新测试递增（Task 1 +62、Task 3 +27），判定只看「是否**新增**失败」。

---

## ⚠️ 执行中发现的测试隔离陷阱（已修复，勿回退）

`tests/test_community_global_mode.py:15` 与 `tests/test_kg_indexed_recall.py:15` 在 import 期用
`if "structlog" not in sys.modules` 往 `sys.modules` 塞一个 `SimpleNamespace` **假 structlog**。

**后果**：只要这两个模块先被收集（字母序靠前，全量跑时必然），`logging_config` 就绑定到假模块，
`get_logger()` 退化成返回 no-op 的 `SimpleNamespace` —— **日志相关测试单独跑通过、全量跑静默失败**。
已在 Task 3 执行中实测复现（`get_logger` 返回 `types.SimpleNamespace`）。

**修复（已落地在 `tests/conftest.py` 顶部）**：`import structlog`。conftest 必先于任何测试模块导入，
真模块进 `sys.modules` 后那两处 stub 的 `not in sys.modules` 条件不成立，stub 自动失效 —— 因此
无需改动那两个模块本身。

**实测验证**：有该行 → 靶序 48 passed / 全量 365 passed；去掉该行 → 靶序出现 2 个失败。
`worker.py` 自身仍用 stdlib `logging.getLogger`（由 Task 13 转换），所以**不要**断言
`worker.logger` 的类型 —— 踩过这个坑：那不是本次要修的问题，误判会掩盖真问题。

**新增任何依赖日志的测试前，确认 conftest 首行仍在。** 后续 Task 6/7/8/12/13 的测试全部依赖它。

---

## 关键约束与已确认决策

### 决策 1：`errors.py` 的**核心**必须 stdlib-only
`worker.py` 走同步线程池、CLI 脚本要复用 —— 若 `errors.py` 顶层引入 pydantic/fastapi，会把它们拉进线程池路径与 CLI。因此**顶层只允许 stdlib**，与 FastAPI 相关的 `register_exception_handlers` **在函数体内**惰性 import。

依赖方向（注意与直觉相反）：

```
errors.py   顶层 stdlib-only（enum / dataclass / 纯函数）
   ▲
   ├── worker.py            (同步线程池)
   ├── routes/*.py          (异步)
   ├── logging_config.py    (脱敏处理器)
   └── errors.register_exception_handlers()
          └── 函数内惰性 import: fastapi, models, logging_config   ← 运行时才建立边
```

**没有 `models.py → errors.py` 这条边**，也不需要：`models.TaskError.code` 本来就是 free-form `str`（`models.py:125`），错误码以**字符串值**喂进去即可，无需 models 认识枚举。真正的边是反方向的、且被惰性化——这正是 `errors.py` 能保持 stdlib-only 的原因。

由 `tests/test_errors.py::test_errors_module_is_stdlib_only` 在**子进程**里断言：`import errors` 后 `sys.modules` 不含 `fastapi`/`pydantic`。

### 决策 2：脱敏处理器位置 = `format_exc_info` **之后**、`JSONRenderer` **之前**
必须先让 `format_exc_info` 把 `exc_info` 元组渲染成 traceback **字符串**，再对该字符串脱敏。否则 `requests`/`httpx` 把 `Authorization: Bearer ...` 写进异常 repr 时会原样落盘。**同时 `exc_info` 必须列入敏感键**（traceback 里可能出现任何东西）。

### 决策 3：`task_id` 用显式 bind，不依赖 contextvars 传播
已实测：中间件里 `cv.set()` 的值**确实**能传入同步 `BackgroundTask` 的线程池（`{"rid": "rid-from-middleware"}`）。但**仍用显式 bind**，理由有三：① 该行为无契约保证，Starlette 版本变更会让关联**静默失效**；② `server.py:143` 的 lifespan 恢复路径**根本没有**请求上下文可继承；③ 继承来的 `request_id` 是"入队请求"的，不是"后台执行"的，需用 `job_phase="background"` 显式区分。

### 决策 4：不扩展 `TaskStatus`，只加 `TaskResult.partial` / `warnings`
`TaskStatus`（`models.py:18`）是 wire 契约，`frontend/src/lib/types.ts` 与 Engine-Vue 消费它。DEGRADED 不是生命周期状态（任务**确实**完成了）、而是质量维度，二者正交。`TaskResult` 加两个带默认值的可选字段是向后兼容的。

### 决策 5：错误响应 `error` + `detail` 双写
新 handler 返回 `{"error": {"code", "message"}, "detail": "<message>"}`。前端与 Engine-Vue 读 `detail` 的现有代码不受影响，新代码可读 `error.code`。**前端改读 `error.code` 后再删除 `detail` 兼容字段** —— 该条件写入本计划收尾项。

### 决策 6：执行顺序「先清代码，最后开规则」
Task 1-15 期间 ruff `select` 为空，CI 保持绿。Task 16 才开启规则。若反过来，CI 会在改造中途长期变红，训练人忽略该 job。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/errors.py` | 错误码枚举 + 分层异常 + 单一映射入口（stdlib-only） | **新建** |
| `backend/tests/test_errors.py` | 错误码可达性 + 映射表完备性守卫 | **新建** |
| `backend/tests/test_worker_mineru_errors.py` | MinerU 失败分类（401/429/5xx/timeout/业务码） | **新建** |
| `backend/tests/test_worker_extraction_outcome.py` | 抽取批次失败语义（全失败/部分失败/零实体三态可分） | **新建** |
| `backend/tests/test_route_error_boundary.py` | 路由不再泄露内部异常文本 | **新建** |
| `backend/tests/test_exception_handlers.py` | 异常边界状态码 + 响应形状 + 不回显用户输入 | **新建** |
| `backend/tests/test_ingest_degraded_status.py` | 任务降级/失败终态可区分 | **新建** |
| `backend/tests/test_log_redaction.py` | 脱敏处理器语料测试 + 过度脱敏反向断言 | **新建** |
| `backend/tests/test_error_handling_policy.py` | 策略守卫（print 清零 / noqa 带理由 / 无裸 except） | **新建** |
| `backend/scripts/purge_log_secrets.py` | 一次性清理已落盘的泄露 token（默认 dry-run） | **新建** |
| `backend/logging_config.py` | 补 `task_id` 绑定 + 脱敏处理器 + `format_exc_info` | 修改 |
| `backend/models.py` | `TaskResult` 加 `partial`/`warnings`；`TaskError` 导入枚举 | 修改 |
| `backend/server.py` | 注册异常边界；移除 `:266` 凭据泄露 | 修改 |
| `backend/worker.py` | MinerU 异常化 + 抽取 outcome + 顶层 raise-through + 日志统一 | 修改 |
| `backend/routes/query.py` | 裸 except 修复 + `detail=str(e)` 泄露修复 | 修改 |
| `backend/routes/bot.py` / `routes/export.py` | `detail=str(e)` 泄露修复 | 修改 |
| `backend/routes/ingest.py` | `progress()` 加 `error_code`/`degraded`；`traceback.print_exc()` 替换 | 修改 |
| `backend/kg_builder.py` / `oss_uploader.py` / `embedding.py` / `doc_processor.py` | 28 处 print 收敛 | 修改 |
| `backend/pyproject.toml` | `[tool.ruff]` + `[tool.bandit]` + dev 依赖加 ruff | 修改 |
| `.github/workflows/ci.yml` | 钉 ruff 版本 + 新增 bandit job | 修改 |
| `docs/governance/sast-exemptions-2026-09-18.md` | SAST 豁免台账（沿用 F002 依赖审计文档体例） | **新建** |
| `.claude/rules/error-handling.md` / `backend/CLAUDE.md` | 基线数字回流（铁律 7） | 修改 |
| `.lra/feature-list.json` / `.lra/progress.txt` | F003/F004 状态回流 | 修改 |

---

## Task 1: 建立 stdlib-only 错误码体系（errors.py）

**Files:**
- Create: `backend/errors.py`
- Create: `backend/tests/test_errors.py`

- [ ] **Step 1: 写 `backend/errors.py` 骨架与枚举**

```python
"""分层错误码与流水线异常基类。

纯 stdlib：可被 worker.py 的线程池同步路径、routes/*.py 的异步路径、
以及 CLI 脚本同时 import，不引入 Pydantic / FastAPI 依赖。
"""
from __future__ import annotations

import enum
import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Mapping


class PipelineStage(str, enum.Enum):
    """失败阶段。与 models.PipelineStage 对齐，但不含 COMPLETED。"""
    MINERU = "mineru"
    BRIDGE = "bridge"
    EXTRACTION = "extraction"
    GROUNDING = "grounding"
    KG_BUILD = "kg_build"
    PARSE = "parse"          # DOCX/XLSX 本地解析路径


class FailureReason(str, enum.Enum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER = "SERVER"
    TIMEOUT = "TIMEOUT"
    PARSE = "PARSE"
    IO = "IO"
    EMPTY = "EMPTY"
    UNKNOWN = "UNKNOWN"


class ErrorCode(str, enum.Enum):
    """二维错误码：PIPELINE_<STAGE>_<REASON>。

    枚举值即 wire 契约，喂入 models.TaskError.code（models.py:124）。
    只收录**可达**组合 —— 不可达成员即 F002 计划所斥的"惰性豁免"。
    例：PIPELINE_BRIDGE_AUTH 无意义（bridge 不做网络 I/O）。
    """
    # ── MINERU（解析，远端 API + 本地 OSS 上传）──
    PIPELINE_MINERU_AUTH = "PIPELINE_MINERU_AUTH"
    PIPELINE_MINERU_RATE_LIMIT = "PIPELINE_MINERU_RATE_LIMIT"
    PIPELINE_MINERU_SERVER = "PIPELINE_MINERU_SERVER"
    PIPELINE_MINERU_TIMEOUT = "PIPELINE_MINERU_TIMEOUT"
    PIPELINE_MINERU_PARSE = "PIPELINE_MINERU_PARSE"
    PIPELINE_MINERU_IO = "PIPELINE_MINERU_IO"
    PIPELINE_MINERU_UNKNOWN = "PIPELINE_MINERU_UNKNOWN"
    PIPELINE_MINERU_ERROR = "PIPELINE_MINERU_ERROR"

    # ── BRIDGE（分段，纯文本变换）──
    PIPELINE_BRIDGE_PARSE = "PIPELINE_BRIDGE_PARSE"
    PIPELINE_BRIDGE_ERROR = "PIPELINE_BRIDGE_ERROR"

    # ── EXTRACTION（LangExtract / Ollama）──
    PIPELINE_EXTRACTION_AUTH = "PIPELINE_EXTRACTION_AUTH"
    PIPELINE_EXTRACTION_RATE_LIMIT = "PIPELINE_EXTRACTION_RATE_LIMIT"
    PIPELINE_EXTRACTION_SERVER = "PIPELINE_EXTRACTION_SERVER"
    PIPELINE_EXTRACTION_TIMEOUT = "PIPELINE_EXTRACTION_TIMEOUT"
    PIPELINE_EXTRACTION_PARSE = "PIPELINE_EXTRACTION_PARSE"
    PIPELINE_EXTRACTION_EMPTY = "PIPELINE_EXTRACTION_EMPTY"
    PIPELINE_EXTRACTION_UNKNOWN = "PIPELINE_EXTRACTION_UNKNOWN"
    PIPELINE_EXTRACTION_ERROR = "PIPELINE_EXTRACTION_ERROR"

    # ── GROUNDING（溯源）──
    PIPELINE_GROUNDING_PARSE = "PIPELINE_GROUNDING_PARSE"
    PIPELINE_GROUNDING_ERROR = "PIPELINE_GROUNDING_ERROR"

    # ── KG_BUILD（建图）──
    PIPELINE_KG_BUILD_IO = "PIPELINE_KG_BUILD_IO"
    PIPELINE_KG_BUILD_ERROR = "PIPELINE_KG_BUILD_ERROR"

    # ── PARSE（DOCX/XLSX 本地路径）──
    PIPELINE_PARSE_IO = "PIPELINE_PARSE_IO"
    PIPELINE_PARSE_PARSE = "PIPELINE_PARSE_PARSE"
    PIPELINE_PARSE_ERROR = "PIPELINE_PARSE_ERROR"

    # ── 请求边界（非流水线）──
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
```

- [ ] **Step 2: 加 `ErrorContext` 与异常层次**

```python
@dataclass(frozen=True)
class ErrorContext:
    """机器可读的失败上下文。"""
    provider: str | None = None       # mineru | ollama | deepseek | oss | feishu
    http_status: int | None = None
    provider_code: Any = None
    task_id: str | None = None
    stage: PipelineStage | None = None
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


class PipelineError(Exception):
    """五阶段流水线统一错误基类。

    __str__ 只返回安全 message —— 这是阻止 detail=str(e) 泄露内部信息的第一道闸。
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    stage: PipelineStage | None = None

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        stage: PipelineStage | None = None,
        context: ErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if stage is not None:
            self.stage = stage
        self.context = context or ErrorContext(stage=self.stage)

    def __str__(self) -> str:
        return self.message

    def to_task_error(self) -> dict[str, str]:
        """转为 models.TaskError 的 dict 形态（喂 routes/ingest.py:71）。"""
        return {"code": self.code.value, "message": self.message}


class StageMinerUError(PipelineError):
    stage = PipelineStage.MINERU
    code = ErrorCode.PIPELINE_MINERU_ERROR


class StageBridgeError(PipelineError):
    stage = PipelineStage.BRIDGE
    code = ErrorCode.PIPELINE_BRIDGE_ERROR


class StageExtractionError(PipelineError):
    stage = PipelineStage.EXTRACTION
    code = ErrorCode.PIPELINE_EXTRACTION_ERROR


class StageGroundingError(PipelineError):
    stage = PipelineStage.GROUNDING
    code = ErrorCode.PIPELINE_GROUNDING_ERROR


class StageKGBuildError(PipelineError):
    stage = PipelineStage.KG_BUILD
    code = ErrorCode.PIPELINE_KG_BUILD_ERROR


class StageParseError(PipelineError):
    stage = PipelineStage.PARSE
    code = ErrorCode.PIPELINE_PARSE_ERROR


class UpstreamUnavailableError(PipelineError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE
```

**注意**：每个阶段一个子类，**不是**每个 (stage, reason) 一个 —— 组合已由 `code` 字段完整表达，按组合拆会是 6×8=48 个近乎相同的类，纯噪声。子类存在的理由是 `.claude/rules/error-handling.md` 要求阶段命名类型，且 `except StageMinerUError` 是有用的捕获粒度。

- [ ] **Step 3: 加单一映射入口 `classify_external_error`**

```python
_PROVIDER_CODE_MAP: dict[str, dict[Any, FailureReason]] = {
    # MinerU 有**两套**失败形态（均实测确认，2026-09-18）：
    #   ① HTTP 状态码非 2xx —— 401/422/429/5xx，响应体**无 code 字段**（用字符串 msgCode）
    #   ② HTTP 200 + 负数 body code —— **业务**失败
    # 因此 worker.py 必须用 `curl -w "%{http_code}"`（`curl -s` 会丢掉状态码，
    # 导致 401 这类"状态码有意义"的失败被误判）。只收录**实测观察到**的码。
    "mineru": {
        # HTTP 200 {"code":-60023,"msg":"this URL is restricted by regional regulations..."}
        -60023: FailureReason.IO,
    },
    # DeepSeek 走标准 HTTP 状态码
    "deepseek": {
        401: FailureReason.AUTH,
        402: FailureReason.AUTH,
        429: FailureReason.RATE_LIMIT,
        500: FailureReason.SERVER,
        503: FailureReason.SERVER,
    },
}

# 只用 HTTP 状态码判定的 provider（无业务码）。新增 provider 须二选一入表，
# 由 tests/test_errors.py::test_all_providers_have_error_class_mapping 强制。
_PROVIDER_HTTP_ONLY: frozenset[str] = frozenset({"ollama", "oss", "feishu"})

_STAGE_ERROR_MAP: dict[PipelineStage, type[PipelineError]] = {
    PipelineStage.MINERU: StageMinerUError,
    PipelineStage.BRIDGE: StageBridgeError,
    PipelineStage.EXTRACTION: StageExtractionError,
    PipelineStage.GROUNDING: StageGroundingError,
    PipelineStage.KG_BUILD: StageKGBuildError,
    PipelineStage.PARSE: StageParseError,
}


def _compose(stage: PipelineStage, reason: FailureReason) -> ErrorCode:
    """PIPELINE_<STAGE>_<REASON> → ErrorCode。缺组合时回退到 stage 通用码。

    这是关键健壮性属性：任何无专属成员的 (stage, reason) 静默降级到
    stage 通用码，而不是在错误处理器里抛 KeyError。
    """
    try:
        return ErrorCode[f"PIPELINE_{stage.name}_{reason.value}"]
    except KeyError:
        return ErrorCode[f"PIPELINE_{stage.name}_ERROR"]


def _extract_http_status(exc: BaseException) -> int | None:
    """从 requests.HTTPError / httpx.HTTPStatusError / oss2 异常提取状态码。

    用 duck-typing 而非 isinstance —— errors.py 必须保持 stdlib-only。
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return status
    status = getattr(exc, "status", None)      # oss2.exceptions.ServerError 形态
    return status if isinstance(status, int) else None


def _is_httpx_timeout(exc: BaseException) -> bool:
    return type(exc).__name__ in ("TimeoutException", "ReadTimeout", "ConnectTimeout")


def _is_httpx_connect_error(exc: BaseException) -> bool:
    return "httpx" in type(exc).__module__ and type(exc).__name__ in (
        "ConnectError", "ConnectTimeout", "ReadError",
    )


def classify_external_error(
    exc: BaseException,
    *,
    stage: PipelineStage,
    provider: str,
    body_code: Any = None,
    task_id: str | None = None,
) -> PipelineError:
    """把外部异常/响应体错误码映射为携带正确 ErrorCode 的 PipelineError。

    单一复用入口：所有外部调用点（MinerU / Ollama / DeepSeek / OSS / 飞书）
    都调用本函数，而非在各处重复 if/elif。

    识别顺序（先具体后一般）：
      1. body_code 命中 provider 映射表（MinerU 的 200+业务码 形态）
      2. 异常类型 → 超时 / 连接 / 响应不可解析
      3. 异常携带的 HTTP 状态码 → 401/403=AUTH, 429=RATE_LIMIT, 5xx=SERVER
      4. 兜底 UNKNOWN
    """
    err_cls = _STAGE_ERROR_MAP[stage]

    if body_code is not None:
        reason = _PROVIDER_CODE_MAP.get(provider, {}).get(body_code)
        if reason is not None:
            return err_cls(
                f"{provider} 返回业务错误码 {body_code}",
                code=_compose(stage, reason),
                context=ErrorContext(
                    provider=provider, provider_code=body_code, stage=stage,
                    task_id=task_id,
                    retryable=reason in (FailureReason.RATE_LIMIT, FailureReason.SERVER),
                ),
            )

    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)) or _is_httpx_timeout(exc):
        return err_cls(
            f"{provider} 请求超时",
            code=_compose(stage, FailureReason.TIMEOUT),
            context=ErrorContext(provider=provider, stage=stage, task_id=task_id,
                                 retryable=True),
        )

    if isinstance(exc, (ConnectionError, OSError)) or _is_httpx_connect_error(exc):
        return err_cls(
            f"{provider} 无法连接",
            code=_compose(stage, FailureReason.SERVER),
            context=ErrorContext(provider=provider, stage=stage, task_id=task_id,
                                 retryable=True),
        )

    if isinstance(exc, (json.JSONDecodeError, ValueError, KeyError, TypeError)):
        return err_cls(
            f"{provider} 响应格式异常",
            code=_compose(stage, FailureReason.PARSE),
            context=ErrorContext(provider=provider, stage=stage, task_id=task_id),
        )

    status = _extract_http_status(exc)
    if status is not None:
        if status in (401, 403):
            reason, msg = FailureReason.AUTH, f"{provider} 凭证无效或过期"
        elif status == 429:
            reason, msg = FailureReason.RATE_LIMIT, f"{provider} 触发限流，请稍后重试"
        elif 500 <= status < 600:
            reason, msg = FailureReason.SERVER, f"{provider} 服务端异常 ({status})"
        else:
            reason, msg = FailureReason.UNKNOWN, f"{provider} 返回异常状态 {status}"
        return err_cls(
            msg, code=_compose(stage, reason),
            context=ErrorContext(provider=provider, http_status=status, stage=stage,
                                 task_id=task_id,
                                 retryable=reason in (FailureReason.RATE_LIMIT,
                                                      FailureReason.SERVER)),
        )

    return err_cls(
        f"{provider} 调用失败",
        code=_compose(stage, FailureReason.UNKNOWN),
        context=ErrorContext(provider=provider, stage=stage, task_id=task_id),
    )
```

- [ ] **Step 4: 加用户可读文案表**

```python
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.PIPELINE_MINERU_AUTH: "文档解析服务凭证无效，请联系管理员检查 MINERU_API_TOKEN。",
    ErrorCode.PIPELINE_MINERU_RATE_LIMIT: "文档解析服务触发限流，请稍后重试。",
    ErrorCode.PIPELINE_MINERU_SERVER: "文档解析服务暂时不可用，请稍后重试。",
    ErrorCode.PIPELINE_MINERU_TIMEOUT: "文档解析超时，请检查文件大小或稍后重试。",
    ErrorCode.PIPELINE_MINERU_PARSE: "文档解析结果格式异常，请联系管理员。",
    ErrorCode.PIPELINE_MINERU_IO: "文档下载或解压失败，请重试。",
    ErrorCode.PIPELINE_MINERU_UNKNOWN: "文档解析失败，请联系管理员。",
    ErrorCode.PIPELINE_MINERU_ERROR: "文档解析失败。",
    ErrorCode.PIPELINE_BRIDGE_PARSE: "文档分段失败，文件结构可能不受支持。",
    ErrorCode.PIPELINE_BRIDGE_ERROR: "文档分段失败。",
    ErrorCode.PIPELINE_EXTRACTION_AUTH: "实体抽取服务凭证无效，请联系管理员。",
    ErrorCode.PIPELINE_EXTRACTION_RATE_LIMIT: "实体抽取服务触发限流，请稍后重试。",
    ErrorCode.PIPELINE_EXTRACTION_SERVER: "实体抽取服务暂时不可用，请稍后重试。",
    ErrorCode.PIPELINE_EXTRACTION_TIMEOUT: "实体抽取超时，请稍后重试。",
    ErrorCode.PIPELINE_EXTRACTION_PARSE: "实体抽取结果格式异常。",
    ErrorCode.PIPELINE_EXTRACTION_EMPTY: "文档已解析，但未能抽取到任何实体（可能不是业务相关文档）。",
    ErrorCode.PIPELINE_EXTRACTION_UNKNOWN: "实体抽取失败，请联系管理员。",
    ErrorCode.PIPELINE_EXTRACTION_ERROR: "实体抽取失败。",
    ErrorCode.PIPELINE_GROUNDING_PARSE: "溯源定位失败，无法匹配原文位置。",
    ErrorCode.PIPELINE_GROUNDING_ERROR: "溯源失败。",
    ErrorCode.PIPELINE_KG_BUILD_IO: "知识图谱写入失败，请检查磁盘空间。",
    ErrorCode.PIPELINE_KG_BUILD_ERROR: "知识图谱构建失败。",
    ErrorCode.PIPELINE_PARSE_IO: "文档读取失败，请检查文件是否损坏。",
    ErrorCode.PIPELINE_PARSE_PARSE: "文档内容解析失败，格式可能不受支持。",
    ErrorCode.PIPELINE_PARSE_ERROR: "文档解析失败。",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误，请联系管理员。",
    ErrorCode.VALIDATION_ERROR: "请求参数校验失败。",
    ErrorCode.UPSTREAM_UNAVAILABLE: "上游服务暂时不可用，请稍后重试。",
}


def user_message(code: ErrorCode) -> str:
    return ERROR_MESSAGES.get(code, "处理失败，请联系管理员。")
```

**分层的意义**：`PipelineError.message` 是**运维向**（如 `"mineru 凭证无效或过期"`），`ERROR_MESSAGES` 是**终端用户向**。HTTP 边界用 `user_message()`，日志行用 `PipelineError.message`。这个拆分使响应体**由构造保证安全**。

- [ ] **Step 5: 写 `backend/tests/test_errors.py`（表驱动）**

```python
"""错误码体系守卫：可达性 + 映射表完备性 + stdlib-only。"""
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (  # noqa: E402
    ERROR_MESSAGES, ErrorCode, ErrorContext, FailureReason, PipelineError,
    PipelineStage, StageExtractionError, StageMinerUError, _compose,
    classify_external_error, user_message,
)

def test_no_unreachable_error_codes():
    """每个枚举成员都必须**可被产出**，否则就是 F002 计划所斥的"惰性豁免"。

    三类成员各有产出路径：
      1. `PIPELINE_<STAGE>_<REASON>` —— 由 _compose(stage, reason) 直接产出
      2. `PIPELINE_<STAGE>_ERROR`   —— 由 _compose 在缺该 (stage, reason) 成员时回退产出
      3. 请求边界码                    —— 仅由 errors.py/异常处理器显式抛出，不在 _compose 像里
    任何不落在这三类里的成员都要被这条测试逮住。

    反例（本测试要能抓到的）：若有人加了 PIPELINE_BRIDGE_AUTH 而 bridge 从不做网络 I/O，
    该成员既不在 _compose 像里（因为 PIPELINE_BRIDGE_AUTH 会被 _compose 命中，
    但没有任何代码会**调用** _compose(BRIDGE, AUTH)）—— 因此还需下面的"已声明产出点"断言。
    """
    boundary = {ErrorCode.INTERNAL_ERROR, ErrorCode.VALIDATION_ERROR,
                ErrorCode.UPSTREAM_UNAVAILABLE}
    producible = {_compose(s, r) for s in PipelineStage for r in FailureReason} | boundary
    unreachable = sorted(c.value for c in ErrorCode if c not in producible)
    assert not unreachable, f"不可产出的错误码成员：{unreachable}"


def test_every_referenced_code_exists():
    """反向守卫：源码里引用的每个 ErrorCode.X 都必须存在。

    防止"改了引用、忘了加成员"导致运行时 KeyError —— 这类错误只在
    真实失败路径上才暴露，测试很难覆盖。
    """
    import re
    from pathlib import Path
    missing = []
    for path in BACKEND.glob("*.py"):
        for ref in re.findall(r"ErrorCode\.([A-Z][A-Z0-9_]+)",
                              path.read_text(encoding="utf-8", errors="replace")):
            if ref not in ErrorCode.__members__:
                missing.append(f"{path.name}: ErrorCode.{ref}")
    assert not missing, f"引用了不存在的错误码：{missing}"


def test_messages_cover_every_code():
    """每个错误码都要有用户可读文案，否则前端只能显示裸码。"""
    missing = sorted(c.value for c in ErrorCode if c not in ERROR_MESSAGES)
    assert not missing, f"缺 ERROR_MESSAGES 文案：{missing}"


def test_user_message_falls_back_safely():
    assert user_message(ErrorCode.INTERNAL_ERROR) == ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR]


@pytest.mark.parametrize("stage", list(PipelineStage))
@pytest.mark.parametrize("reason", list(FailureReason))
def test_compose_never_raises(stage, reason):
    """任何 (stage, reason) 组合都必须返回 ErrorCode，缺成员时回退通用码。"""
    code = _compose(stage, reason)
    assert isinstance(code, ErrorCode)


def test_compose_prefers_specific_over_generic():
    assert _compose(PipelineStage.MINERU, FailureReason.AUTH) is ErrorCode.PIPELINE_MINERU_AUTH
    # BRIDGE 无 AUTH 成员 → 必须回退到 BRIDGE 通用码，而不是 KeyError
    assert _compose(PipelineStage.BRIDGE, FailureReason.AUTH) is ErrorCode.PIPELINE_BRIDGE_ERROR


def test_classify_timeout():
    import subprocess as sp
    err = classify_external_error(sp.TimeoutExpired("curl", 30),
                                  stage=PipelineStage.MINERU, provider="mineru")
    assert err.code is ErrorCode.PIPELINE_MINERU_TIMEOUT
    assert err.context.retryable is True


def test_classify_http_401_is_auth():
    """MinerU 鉴权失败走 **HTTP 状态码**（实测 401），不走 body 业务码。

    ⚠️ 本测试初版断言 body_code=-10001 优先，那个数字**是编造的**、已推翻：
    真实响应体用字符串 msgCode（"A0202"）且没有 code 字段。
    """
    err = classify_external_error(_http_status_error(401),
                                  stage=PipelineStage.MINERU, provider="mineru")
    assert err.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert err.context.retryable is False


def test_mineru_has_no_body_code_map():
    """回归守卫：MinerU 的 _PROVIDER_CODE_MAP 必须为空（勿再填入编造的负数码）。"""
    assert _PROVIDER_CODE_MAP["mineru"] == {}


def test_classify_parse_error():
    import json
    err = classify_external_error(json.JSONDecodeError("x", "", 0),
                                  stage=PipelineStage.EXTRACTION, provider="ollama")
    assert err.code is ErrorCode.PIPELINE_EXTRACTION_PARSE


def test_classify_http_429():
    class _Resp:
        status_code = 429
    class _HttpError(Exception):
        response = _Resp()
    err = classify_external_error(_HttpError(), stage=PipelineStage.EXTRACTION, provider="deepseek")
    assert err.code is ErrorCode.PIPELINE_EXTRACTION_RATE_LIMIT
    assert err.context.retryable is True


def test_classify_http_401_is_not_retryable():
    class _Resp:
        status_code = 401
    class _HttpError(Exception):
        response = _Resp()
    err = classify_external_error(_HttpError(), stage=PipelineStage.MINERU, provider="mineru")
    assert err.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert err.context.retryable is False


def test_all_providers_have_error_class_mapping():
    """新增 provider 必须二选一入表，防止漏配后静默降级为 UNKNOWN。"""
    from errors import _PROVIDER_CODE_MAP, _PROVIDER_HTTP_ONLY
    known = set(_PROVIDER_CODE_MAP) | set(_PROVIDER_HTTP_ONLY)
    assert known == {"mineru", "deepseek", "ollama", "oss", "feishu"}


def test_str_returns_safe_message_only():
    """__str__ 不得暴露原始异常 —— 这是阻止 detail=str(e) 泄露的第一道闸。"""
    err = StageMinerUError("MinerU 凭证无效", code=ErrorCode.PIPELINE_MINERU_AUTH)
    assert str(err) == "MinerU 凭证无效"


def test_stage_subclass_carries_default_code():
    err = StageExtractionError("抽取失败")
    assert err.stage is PipelineStage.EXTRACTION
    assert err.code is ErrorCode.PIPELINE_EXTRACTION_ERROR
    assert isinstance(err, PipelineError)


def test_errors_module_is_stdlib_only():
    """errors.py 不得把 pydantic/fastapi 拉进线程池路径与 CLI。"""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); import errors; "
         "bad=[m for m in ('fastapi','pydantic') if m in sys.modules]; "
         "print('|'.join(bad))" % BACKEND],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", f"errors.py 引入了非 stdlib 依赖：{proc.stdout}"
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_errors.py -q --no-header`
Expected: 全部通过（`test_compose_never_raises` 会展开 6 阶段 × 8 失败类 = 48 个参数组合；`ErrorCode` 共 28 个成员 —— 25 个 `PIPELINE_*` + 3 个边界码）

- [ ] **Step 7: Commit**

```bash
git add backend/errors.py backend/tests/test_errors.py
git commit -m "feat(errors): 建立分层错误码体系（阶段×失败类，stdlib-only）"
```

---

## Task 2: `logging_config.py` 补 `task_id` 绑定

**Files:**
- Modify: `backend/logging_config.py`

- [ ] **Step 1: 加 `task_id` 上下文与作用域管理器**

在 `logging_config.py` 的 `request_id_var` 声明（`:19`）之后追加：

```python
task_id_var: ContextVar[str] = ContextVar("task_id", default="")
```

在 `get_request_id()`（`:111-113`）之后追加：

```python
def bind_task_context(task_id: str) -> None:
    """绑定 task_id 到 structlog 上下文。在 run_real_pipeline 顶部调用。

    显式绑定，不依赖 contextvars 从请求上下文继承 —— 该继承行为已实测可行
    但无契约保证，且 server.py:143 的 lifespan 恢复路径根本没有请求上下文。

    job_phase="background" 用于区分：此处可能继承来的 request_id 是
    **入队请求**的 id，不是当前执行请求的 id。
    """
    task_id_var.set(task_id)
    structlog.contextvars.bind_contextvars(task_id=task_id, job_phase="background")


def clear_task_context() -> None:
    task_id_var.set("")
    structlog.contextvars.unbind_contextvars("task_id", "job_phase")


def get_task_id() -> str:
    return task_id_var.get()


@contextmanager
def task_scope(task_id: str):
    """上下文管理器形态 —— 保证异常路径也解绑。"""
    bind_task_context(task_id)
    try:
        yield
    finally:
        clear_task_context()
```

头部 import 补 `from contextlib import contextmanager`。

- [ ] **Step 2: 验证绑定生效**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "
import logging, io, logging_config
logging_config.setup_logging('/tmp/t')
buf = io.StringIO(); h = logging.StreamHandler(buf)
h.setFormatter(logging.Formatter('%(message)s')); logging.getLogger().addHandler(h)
with logging_config.task_scope('task-abc'):
    logging_config.get_logger('t').info('inside')
logging_config.get_logger('t').info('outside')
print(buf.getvalue())
"
```
Expected: `inside` 行含 `"task_id": "task-abc"` 与 `"job_phase": "background"`；`outside` 行**不含**这两个字段（解绑生效）。

- [ ] **Step 3: Commit**

```bash
git add backend/logging_config.py
git commit -m "feat(logging): 补 task_id 上下文绑定与 task_scope 作用域管理器"
```

---

## Task 3: 日志脱敏处理器

**Files:**
- Modify: `backend/logging_config.py`
- Create: `backend/tests/test_log_redaction.py`

- [ ] **Step 1: 写失败测试（TDD）**

```python
"""脱敏处理器语料测试：该脱的必须脱，不该脱的不能动。"""
import io
import json
import logging
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import logging_config  # noqa: E402


@pytest.fixture
def capture():
    logging_config.setup_logging("/tmp/test_redact_logs")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
    yield lambda: json.loads(buf.getvalue().strip().splitlines()[-1])
    logging.getLogger().removeHandler(handler)


@pytest.mark.parametrize("key", [
    "api_key", "apiKey", "access_token", "secret", "password", "passwd",
    "authorization", "Authorization", "credential", "client_secret", "file_access_token",
])
def test_sensitive_keys_are_redacted(capture, key):
    logging_config.get_logger("t").info("probe", **{key: "SUPER-SECRET-VALUE"})
    assert capture()[key] == "[REDACTED]", f"{key} 未脱敏"


def test_value_patterns_redacted_under_innocent_key(capture):
    """键名无害但值是密钥形态 —— 仍须脱敏。"""
    logging_config.get_logger("t").info("probe", note="Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    assert "[REDACTED]" in capture()["note"]


@pytest.mark.parametrize("value", [
    "sk-FAKE_TEST_PLACEHOLDER_000000000000",
    "sk-abcd1234efgh5678",
    "LTAI5t7DjHhjuhJ596MXHV3P",
    "ghp_FAKE_TEST_PLACEHOLDER_0000000000000000",
])
def test_known_secret_shapes_redacted(capture, value):
    logging_config.get_logger("t").info("probe", blob=value)
    assert "[REDACTED]" in capture()["blob"]


def test_nested_dicts_are_scrubbed(capture):
    logging_config.get_logger("t").info("probe", outer={"inner": {"token": "X"}})
    assert capture()["outer"]["inner"]["token"] == "[REDACTED]"


def test_lists_are_scrubbed(capture):
    logging_config.get_logger("t").info("probe", items=[{"api_key": "X"}, "Bearer abcdefghijklmnop"])
    got = capture()["items"]
    assert got[0]["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in got[1]


def test_exc_info_secret_is_scrubbed_and_traceback_survives(capture):
    """requests/httpx 会把 Authorization 头写进异常 repr，traceback 字符串必须脱敏；
    但同时**必须保留 traceback** —— 整条丢掉比泄露更糟（诊断价值归零）。

    保护机制是**值扫描**而非键名：format_exc_info 在 redact_sensitive 之前
    已把 exc_info 键改名为 exception，故键名规则对 traceback 无效。
    """
    try:
        raise ValueError("auth failed for Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    except ValueError:
        logging_config.get_logger("t").error("boom", exc_info=True)
    entry = capture()
    rendered = json.dumps(entry)
    # 密钥形态被替换
    assert "eyJhbGciOiJIUzI1NiJ9" not in rendered
    assert "[REDACTED]" in rendered
    # traceback 本体仍在（否则本特性毫无诊断价值）
    assert "exception" in entry, "traceback 字段丢失"
    assert "Traceback" in entry["exception"] or "ValueError" in entry["exception"]
    assert "auth failed for" in entry["exception"]


@pytest.mark.parametrize("key", ["task_id", "stage", "latency_ms", "path", "request_id", "node_count"])
# 注意：不要加 "event" —— structlog 的 BoundLogger.info(self, event=None, **kw) 把 event 用作
# 位置参数键，`.info("probe", event="x")` 会抛 TypeError: got multiple values for argument 'event'，
# 该参数组合永远跑不通。
def test_benign_fields_are_not_redacted(capture, key):
    """反向断言：过度脱敏会让日志失去诊断价值。"""
    logging_config.get_logger("t").info("probe", **{key: "sensible-value"})
    assert capture()[key] == "sensible-value", f"{key} 被误脱敏"


def test_benign_value_containing_sk_prefix_survives_rest(capture):
    """值里嵌了 sk- 形态时只替换命中片段，其余内容保留。"""
    logging_config.get_logger("t").info("probe", note="entity sk-abcd1234efgh5678 appeared on page 3")
    got = capture()["note"]
    assert "[REDACTED]" in got
    assert "appeared on page 3" in got


def test_depth_bound_prevents_runaway(capture):
    deep = cur = {}
    for _ in range(12):
        cur["n"] = {}
        cur = cur["n"]
    cur["token"] = "X"
    logging_config.get_logger("t").info("probe", deep=deep)   # 不得栈溢出或超时
    assert "probe" == capture()["event"]
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_log_redaction.py -q --no-header`
Expected: FAIL（键未脱敏、值为 `SUPER-SECRET-VALUE` 原样落盘）

- [ ] **Step 3: 实现处理器**

在 `logging_config.py` 追加（`import re` 与 `from typing import Any, Mapping`）：

```python
REDACTED = "[REDACTED]"
_MAX_DEPTH = 6
_MAX_ITEMS = 200

# 键名匹配：必须整段命中（(?:^|_)...(?:$|_)），避免 author_name 误命中 auth
#
# 注意**不要**把 exc_info / exception 加进来：
#   - format_exc_info 在 redact_sensitive **之前**运行，会 pop 掉 exc_info 键、
#     改名为 exception —— 因此 "exc_info" 写在正则里是永远匹配不到的死条目。
#   - 把 "exception" 加进来则会**整条丢弃 traceback**，诊断价值归零，比泄露更糟。
# 因此 traceback 的保护靠的是**值扫描**（见下），不是键名。残留缺口：
# 若密钥以不匹配任何值模式的形态（如异常消息里一段裸 16 位 hex）出现在 traceback 中，
# 不会被捕获 —— 这是已知取舍，由 tests/test_log_redaction.py::test_exc_info_* 覆盖现状。
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:token|key|secret|password|passwd|pwd|auth|authorization|"
    r"credential|session|signature|cookie|dsn)(?:$|_)",
    re.IGNORECASE,
)
# 驼峰/无分隔形态：apiKey / accessToken / clientSecret
_SENSITIVE_KEY_SUFFIX_RE = re.compile(
    r"(?:apikey|accesskey|secretkey|token|secret|password|passwd|authorization|credential)$",
    re.IGNORECASE,
)

_SENSITIVE_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-graphrag-[A-Za-z0-9_\-]{6,}\b"),                 # 本项目 API Key 前缀（先于通用 sk-）
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),                          # OpenAI/DeepSeek
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),  # JWT
    re.compile(r"\bLTAI[A-Za-z0-9]{12,}\b"),                           # 阿里云 AccessKeyId
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),                              # AWS AccessKeyId
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),                           # GitHub PAT
)

# FILE_ACCESS_TOKEN 形态（security.py:7 = sha256 hex[:16]）。单独用误报率高，
# 故仅在**键名也命中**时才应用。
_HEX_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{16,64}$")


def _scrub_scalar(value: Any, *, key_hit: bool) -> Any:
    if not isinstance(value, str):
        return value
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        if pattern.search(value):
            return pattern.sub(REDACTED, value)
    if key_hit and _HEX_TOKEN_RE.match(value.strip()):
        return REDACTED
    return value


def _scrub(obj: Any, *, key_hit: bool = False, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(obj, str):
        return _scrub_scalar(obj, key_hit=key_hit)
    if isinstance(obj, BaseException):
        return f"{type(obj).__name__}: {_scrub_scalar(str(obj), key_hit=key_hit)}"
    if isinstance(obj, Mapping):
        out: dict[Any, Any] = {}
        for k, v in list(obj.items())[:_MAX_ITEMS]:
            hit = key_hit or bool(
                _SENSITIVE_KEY_RE.search(str(k)) or _SENSITIVE_KEY_SUFFIX_RE.search(str(k))
            )
            out[k] = REDACTED if hit else _scrub(v, key_hit=hit, depth=depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        items = [_scrub(v, key_hit=key_hit, depth=depth + 1) for v in obj[:_MAX_ITEMS]]
        return type(obj)(items) if isinstance(obj, tuple) else items
    if isinstance(obj, (set, frozenset)):
        return type(obj)(_scrub(v, key_hit=key_hit, depth=depth + 1) for v in list(obj)[:_MAX_ITEMS])
    return obj


def redact_sensitive(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor：递归脱敏 event_dict 中的密钥类键与值。

    位置：format_exc_info **之后**、JSONRenderer **之前**。
    必须先让 format_exc_info 把 exc_info 元组渲染成 traceback 字符串，
    再对整条 event_dict（含 traceback，其中可能内嵌 Authorization 头）脱敏。
    """
    for key, value in list(event_dict.items()):
        hit = bool(
            _SENSITIVE_KEY_RE.search(str(key)) or _SENSITIVE_KEY_SUFFIX_RE.search(str(key))
        )
        event_dict[key] = REDACTED if hit else _scrub(value, key_hit=hit)
    return event_dict
```

- [ ] **Step 4: 接入 processor 链（同时补 `format_exc_info`）**

把 `logging_config.py:83-95` 的 `processors` 列表改为：

```python
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            # 先把 exc_info 渲染成 traceback 字符串（否则 exc_info=True 只输出 true，
            # 堆栈被静默丢弃 —— 这是改造前的实测缺陷）。
            structlog.processors.format_exc_info,
            # 再对整条 event_dict（含 traceback 字符串）脱敏。
            # 注意：本处理器之后不得再插入会重新引入原始值的 processor。
            redact_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_log_redaction.py -q --no-header`
Expected: PASS

- [ ] **Step 6: 验证 traceback 现在真的落盘**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "
import logging, io, logging_config
logging_config.setup_logging('/tmp/t')
buf = io.StringIO(); h = logging.StreamHandler(buf)
h.setFormatter(logging.Formatter('%(message)s')); logging.getLogger().addHandler(h)
try:
    raise ValueError('boom')
except ValueError:
    logging_config.get_logger('t').error('probe', exc_info=True)
out = buf.getvalue()
print('HAS_TRACEBACK:', 'Traceback' in out or 'ValueError' in out)
print(out[:300])
"
```
Expected: `HAS_TRACEBACK: True`

- [ ] **Step 7: Commit**

```bash
git add backend/logging_config.py backend/tests/test_log_redaction.py
git commit -m "feat(logging): 新增脱敏处理器并修复 traceback 被静默丢弃"
```

---

## Task 4: 清除 `server.py:266` 的凭据泄露

**Files:**
- Modify: `backend/server.py:266`
- Modify: `backend/security.py:15`（过期 docstring）

- [ ] **Step 1: 替换泄露的日志调用**

`backend/server.py:266`：
```python
    logger.info("server_started", file_access_token=FILE_ACCESS_TOKEN)
```
改为：
```python
    # 不得输出 token 值 —— 该 token 是 routes/documents.py:132 文件访问的 bearer 凭据。
    # 字段名刻意不含 "token"：脱敏处理器的键名规则会把任何含 token 段的键整体替换为
    # [REDACTED]，那样这个布尔值本身也会被抹掉、日志失去意义。
    logger.info("server_started", file_access_enabled=bool(FILE_ACCESS_TOKEN))
```

⚠️ **字段名陷阱（实测踩到）**：初版写成 `file_access_token_set=bool(...)`，结果被 Task 3 的脱敏处理器整键替换为 `"file_access_enabled": "[REDACTED]"` —— 密钥确实没泄露，但这个布尔值也读不出来了，日志失去意义。脱敏规则是按**键名含 `token` 段**整体替换，不看值类型。**字段名必须避开 token/key/secret 等敏感段。**

- [ ] **Step 2: 修正 `security.py` 的过期 docstring**

`backend/security.py:15` 的 `get_file_access_token()` docstring 若含 "(printed at startup)" 类描述，改为反映实际行为（token 不落日志）。

- [ ] **Step 3: 验证不再落盘**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "
import logging, io, json, logging_config
logging_config.setup_logging('/tmp/t')
buf = io.StringIO(); h = logging.StreamHandler(buf)
h.setFormatter(logging.Formatter('%(message)s')); logging.getLogger().addHandler(h)
from security import FILE_ACCESS_TOKEN
logging_config.get_logger('s').info('server_started', file_access_enabled=bool(FILE_ACCESS_TOKEN))
rec = json.loads(buf.getvalue().strip().splitlines()[-1])
assert FILE_ACCESS_TOKEN not in buf.getvalue(), 'token 仍落盘'
assert rec['file_access_enabled'] is True, f'布尔值被脱敏抹掉: {rec}'
print('OK: token 未出现，且布尔值可读')
"
```
Expected: `OK: token 未出现，且布尔值可读`

- [ ] **Step 4: Commit**

```bash
git add backend/server.py backend/security.py
git commit -m "security(server): 停止在启动日志中输出 file_access_token 明文"
```

---

## Task 5: 清理已落盘的 3 个泄露 token

**Files:**
- Create: `backend/scripts/purge_log_secrets.py`

**前置确认（已侦察，仍须复验）**：`output/logs/` 已被 `backend/.gitignore:11` 忽略且未跟踪 → 本任务**不涉及** git 历史清理。执行前先跑 `git check-ignore -v output/logs/app.log` 复验；若退出码非 0（即已被跟踪），**停止并向项目负责人升级**，不得自行决定历史改写。

- [ ] **Step 1: 写清理脚本（默认 dry-run）**

```python
"""一次性清理 output/logs 中已落盘的密钥形态。

默认 dry-run；加 --apply 才实际改写。
原子替换（写临时文件 + Path.replace）以防中断损坏日志。
可重复执行（幂等）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
LOG_DIR = BACKEND / "output" / "logs"

# (pattern, replacement) 显式配对 —— 比在 subn 里判断 match.groups 可读，
# 也避免"某天改了捕获组数量导致替换静默变形"。
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 已知泄露形态：file_access_token 键后跟 16-64 位 hex
    (re.compile(r'("file_access_token"\s*:\s*)"[0-9a-fA-F]{16,64}"'), r'\1"[REDACTED]"'),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"), "[REDACTED]"),
    (re.compile(r"\bLTAI[A-Za-z0-9]{12,}\b"), "[REDACTED]"),
)


def scrub_text(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in _PATTERNS:
        text, n = pattern.subn(replacement, text)
        count += n
    return text, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入（默认仅预览）")
    args = ap.parse_args()

    if not LOG_DIR.exists():
        print(f"日志目录不存在，无需清理：{LOG_DIR}")
        return 0

    total = 0
    for path in sorted(LOG_DIR.rglob("*.log*")):
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        scrubbed, n = scrub_text(original)
        if n == 0:
            continue
        total += n
        print(f"{'改写' if args.apply else '将改写'} {path.name}: {n} 处")
        if args.apply:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(scrubbed, encoding="utf-8")
            tmp.replace(path)
    print(f"{'已' if args.apply else '将'}清理 {total} 处")
    if not args.apply and total:
        print("加 --apply 执行实际清理。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: dry-run 预览**

Run: `cd backend && .venv/Scripts/python.exe scripts/purge_log_secrets.py`
Expected: 报告 **126 处**（分布在 9 个轮转文件；`app.log` 本身 0 处）；文件未改动。

- [ ] **Step 3: 实际清理并验证**

Run:
```bash
cd backend && .venv/Scripts/python.exe scripts/purge_log_secrets.py --apply && \
  echo "残留（应 0）: $(grep -ho 'file_access_token": "[0-9a-f]\{16,64\}"' output/logs/app.log* | wc -l)" && \
  echo "已脱敏: $(grep -h file_access_token output/logs/app.log* | grep -c REDACTED)"
```
Expected: `残留（应 0）: 0`、`已脱敏: 126`

**注意必须用 `output/logs/app.log*` 通配**覆盖轮转文件 —— 只查 `app.log` 会得到"0 残留"的**假成功**（`app.log` 本来就没有泄露值）。

- [ ] **Step 4: 验证幂等**

Run: `cd backend && .venv/Scripts/python.exe scripts/purge_log_secrets.py --apply`
Expected: `已清理 0 处`

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/purge_log_secrets.py
git commit -m "security(logs): 新增日志密钥清理脚本并清除 126 处已落盘的 file_access_token"
```

---

## Task 6: `worker._call_mineru_api` 异常化（BEHAVIOR）

**Files:**
- Modify: `backend/worker.py:938-1013`
- Create: `backend/tests/test_worker_mineru_errors.py`

**这是行为变更**：`_call_mineru_api` 由「7 处 `return None`」改为「一律 raise `StageMinerUError`」，返回类型 `str | None` → `str`。调用方需在 Task 8 同步。

- [ ] **Step 1: 写失败测试**

```python
"""MinerU 失败分类：401/429/5xx/timeout/业务码 必须可分。

按项目宪章铁律 5：不 mock 被测逻辑，只在进程边界 monkeypatch subprocess.run。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import ErrorCode, StageMinerUError  # noqa: E402
import worker  # noqa: E402


def _fake_run(stdout: str, exc=None):
    def _run(cmd, **kwargs):
        if exc is not None:
            raise exc
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return _run


def test_submit_http_401_raises_auth(monkeypatch):
    """MinerU 的鉴权失败是 **HTTP 401 + 无 code 字段**（实测）：
        HTTP 401 {"msgCode":"A0202","msg":"user authenticate failed","success":false}
    必须靠 `curl -w "%{http_code}"` 取回状态码 —— `curl -s` 会丢掉它。
    ⚠️ 本测试初版断言的是 body code=-10001，那个数字**无依据**、已推翻。"""
    body = json.dumps({"msgCode": "A0202", "msg": "user authenticate failed",
                       "success": False, "data": None})
    monkeypatch.setattr(subprocess, "run", _fake_run(f"{body}
401"))
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert ei.value.context.retryable is False


def test_submit_http_429_raises_rate_limit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run('{"msg":"too many"}\n429'))
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_RATE_LIMIT
    assert ei.value.context.retryable is True


def test_submit_timeout_raises_timeout(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        _fake_run("", exc=subprocess.TimeoutExpired("curl", 35)))
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_TIMEOUT


def test_submit_unparseable_body_raises_parse(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("<html>502 Bad Gateway</html>"))
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_PARSE


def test_poll_state_failed_raises_server(monkeypatch):
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(cmd, 0,
                stdout=json.dumps({"code": 0, "data": {"task_id": "mt1"}}), stderr="")
        return subprocess.CompletedProcess(cmd, 0,
            stdout=json.dumps({"code": 0, "data": {"state": "failed"}}), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_SERVER


def test_poll_timeout_raises_timeout(monkeypatch):
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(cmd, 0,
                stdout=json.dumps({"code": 0, "data": {"task_id": "mt1"}}), stderr="")
        return subprocess.CompletedProcess(cmd, 0,
            stdout=json.dumps({"code": 0, "data": {"state": "running"}}), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_TIMEOUT


def test_poll_auth_failure_does_not_retry_120_times(monkeypatch):
    """硬鉴权失败重试无意义 —— 必须立即抛出。"""
    class _Fake401(Exception):
        class response:
            status_code = 401

    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(cmd, 0,
                stdout=json.dumps({"code": 0, "data": {"task_id": "mt1"}}), stderr="")
        raise _Fake401()

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    with pytest.raises(StageMinerUError):
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert calls["n"] <= 3, f"鉴权失败不应反复重试，实际调用 {calls['n']} 次"
```

**注意 `classify_external_error` 的判定顺序对测试 4 是承重的**：`json.JSONDecodeError` 是 `ValueError` 的子类，二者同在 PARSE 分支、结论一致，所以顺序无影响；但若将来把 `ValueError` 从 PARSE 分支挪走，`test_submit_unparseable_body_raises_parse`（返 HTML 导致 JSON 解码失败）会先落到别处。改动该分支时必须重跑本测试文件。

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_worker_mineru_errors.py -q --no-header`
Expected: FAIL（当前返回 `None`，不抛异常）

- [ ] **Step 3: 改造 `_call_mineru_api`**

先补 import。`worker.py` 顶部 import 区（`from kg_builder import ...` 之后）加：

```python
from errors import (
    ErrorCode, ErrorContext, PipelineError, PipelineStage,
    StageMinerUError, classify_external_error,
)
from logging_config import get_logger
logger = get_logger(__name__)      # 替换原有的 logger = logging.getLogger(__name__)
```

然后用下面**完整**的实现替换 `worker.py:938-1013` 整个 `_call_mineru_api` 函数（签名 `-> str`，原 7 处 `return None` 全部消失）：

```python
def _call_mineru_api(file_url: str, token: str, task_id: str,
                     ingest_options: dict | None = None) -> str:
    """提交 MinerU、轮询、下载解压，返回输出目录。

    失败一律 raise StageMinerUError —— 不再 return None，
    使调用方能区分 401 / 429 / 5xx / timeout / 业务码。
    """
    base = os.getenv("MINERU_API_BASE_URL", "https://mineru.net/api/v4/extract/task")

    opts = ingest_options or {}
    language = opts.get("language", "ch")
    enable_formula = bool(opts.get("enable_formula", True))
    enable_table = bool(opts.get("enable_table", True))
    model_version = opts.get("model_version", "pipeline")

    payload = json.dumps({
        "url": file_url,
        "language": language,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "model_version": model_version,
    })

    # ── 提交 ──────────────────────────────────────────────────────────────
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-X", "POST", base,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {token}", "-d", payload],
            capture_output=True, text=True, timeout=35,
        )
        data = json.loads(result.stdout)
    except subprocess.TimeoutExpired as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        # 例如 curl 拿到 HTML 错误页而非 JSON
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc

    if data.get("code") != 0:
        # MinerU 的业务失败是 HTTP 200 + body code != 0，必须靠 body_code 分类，
        # 否则鉴权失败会退化成笼统的"提交失败"，与超时无法区分。
        raise classify_external_error(
            RuntimeError("mineru submit failed"),
            stage=PipelineStage.MINERU, provider="mineru",
            body_code=data.get("code"), task_id=task_id,
        )

    try:
        mineru_task_id = data["data"]["task_id"]
    except (KeyError, TypeError) as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc

    # ── 轮询 ──────────────────────────────────────────────────────────────
    zip_url: str | None = None
    for _ in range(120):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "20", f"{base}/{mineru_task_id}",
                 "-H", f"Authorization: Bearer {token}"],
                capture_output=True, text=True, timeout=25,
            )
            data = json.loads(result.stdout)["data"]
            if data["state"] == "done":
                zip_url = data["full_zip_url"]
                break
            if data["state"] == "failed":
                raise StageMinerUError(
                    "MinerU 解析任务失败",
                    code=ErrorCode.PIPELINE_MINERU_SERVER,
                    context=ErrorContext(
                        provider="mineru", stage=PipelineStage.MINERU,
                        task_id=task_id,
                        details={"mineru_task_id": mineru_task_id},
                    ),
                )
        except StageMinerUError:
            raise
        except subprocess.TimeoutExpired:
            # 单次轮询超时属正常抖动，继续轮询
            logger.warning("mineru_poll_timeout", task_id=task_id,
                           mineru_task_id=mineru_task_id, exc_info=True)
        except Exception as exc:
            mapped = classify_external_error(
                exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
            )
            if not mapped.context.retryable:
                # 401/403/解析失败：重试 120 次毫无意义，立即抛出
                raise mapped from exc
            logger.warning("mineru_poll_retry", task_id=task_id,
                           mineru_task_id=mineru_task_id,
                           error_code=mapped.code.value, exc_info=True)
        time.sleep(5)
    else:
        raise StageMinerUError(
            "MinerU 轮询超时（120 次）",
            code=ErrorCode.PIPELINE_MINERU_TIMEOUT,
            context=ErrorContext(
                provider="mineru", stage=PipelineStage.MINERU, task_id=task_id,
                provider_code="poll_timeout", retryable=True,
                details={"mineru_task_id": mineru_task_id},
            ),
        )

    # ── 下载并解压 ────────────────────────────────────────────────────────
    output_dir = os.path.join(os.path.dirname(__file__), "output", "mineru", task_id[:8])
    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, "result.zip")
    try:
        subprocess.run(["curl", "-s", "-o", zip_path, zip_url],
                       check=True, timeout=120)
        subprocess.run(["unzip", "-o", zip_path, "-d", output_dir],
                       check=True, timeout=30)
        os.remove(zip_path)
    except subprocess.TimeoutExpired as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        # curl/unzip 非零退出、磁盘写入失败 → IO 类
        raise StageMinerUError(
            "MinerU 结果下载或解压失败",
            code=ErrorCode.PIPELINE_MINERU_IO,
            context=ErrorContext(
                provider="mineru", stage=PipelineStage.MINERU, task_id=task_id,
                retryable=True, details={"mineru_task_id": mineru_task_id},
            ),
        ) from exc

    return output_dir
```

**要点**：`except StageMinerUError: raise` 必须排在轮询的 `except Exception` **之前** —— 否则上面主动抛出的 `PIPELINE_MINERU_SERVER` 会被下面的宽捕重新分类成 `UNKNOWN`。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_worker_mineru_errors.py -q --no-header`
Expected: PASS

- [ ] **Step 5: 确认既有 worker 测试未回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header -k "worker or runtime_index"`

- [ ] **Step 6: Commit**

```bash
git add backend/worker.py backend/tests/test_worker_mineru_errors.py
git commit -m "fix(worker): MinerU 客户端失败语义由 return None 收敛为分层异常"
```

---

## Task 7: 抽取批次失败语义（BEHAVIOR，正确性修复）

**Files:**
- Modify: `backend/worker.py:829-909`
- Create: `backend/tests/test_worker_extraction_outcome.py`

**这是本轮最重要的一处正确性修复**：`worker.py:870` 的 `except Exception: continue` 让失败的抽取批次被静默跳过，`worker.py:899` 返回 `(0,0)`，调用方无法区分「文档确实无实体」与「Ollama 挂了」。

- [ ] **Step 1: 写失败测试**

```python
"""抽取三态可分：全失败 / 部分失败 / 零实体 —— 改造前全部退化为 (0,0)。"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import ErrorCode, StageExtractionError  # noqa: E402
import worker  # noqa: E402


class _Chunk:
    def __init__(self, text):
        self.text = text


def _chunks(n=10):
    return [_Chunk(f"文档内容第 {i} 段") for i in range(n)]


def _stub_ollama(monkeypatch, *, fail_first_n: int, entities: bool = True):
    """用本地假响应替换 requests.post，只替换进程边界。"""
    import requests
    state = {"n": 0}

    class _Resp:
        def __init__(self):
            self._ok = True

        def raise_for_status(self):
            if not self._ok:
                raise requests.HTTPError("500 Server Error", response=type("R", (), {"status_code": 500})())

        def json(self):
            if entities:
                return {"message": {"content": '{"entities":[{"name":"设备A","type":"设备"}],"relations":[]}'}}
            return {"message": {"content": '{"entities":[],"relations":[]}'}}

    def _post(url, **kwargs):
        state["n"] += 1
        r = _Resp()
        if state["n"] <= fail_first_n:
            r._ok = False
        return r

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(worker.os.path, "exists", lambda p: True)
    return state


def test_all_batches_failed_raises(monkeypatch):
    """Ollama 全挂 —— 必须 raise，而不是伪装成 (0,0) 成功。"""
    _stub_ollama(monkeypatch, fail_first_n=999)
    with pytest.raises(StageExtractionError) as ei:
        worker._extract_and_build_kg(_chunks(), "t1", "f.pdf")
    assert ei.value.code is ErrorCode.PIPELINE_EXTRACTION_EMPTY
    assert ei.value.context.details["batches_total"] == 2
    assert ei.value.context.details["batches_failed"] == 2


def test_partial_failure_is_marked_partial(monkeypatch):
    _stub_ollama(monkeypatch, fail_first_n=1)
    outcome = worker._extract_and_build_kg(_chunks(), "t1", "f.pdf")
    assert outcome.partial is True
    assert outcome.batches_total == 2
    assert outcome.batches_failed == 1
    assert outcome.node_count > 0


def test_zero_entities_is_not_confused_with_failure(monkeypatch):
    """文档确实无实体 —— 必须与「全失败」产出不同结果。"""
    _stub_ollama(monkeypatch, fail_first_n=0, entities=False)
    outcome = worker._extract_and_build_kg(_chunks(), "t1", "f.pdf")
    assert outcome.batches_failed == 0
    assert outcome.all_failed is False
    assert outcome.node_count == 0


def test_all_failed_and_zero_entity_are_distinguishable(monkeypatch):
    """回归守卫：改造前这两种情况都返回 (0,0)。"""
    _stub_ollama(monkeypatch, fail_first_n=999)
    with pytest.raises(StageExtractionError):
        worker._extract_and_build_kg(_chunks(), "t1", "f.pdf")

    _stub_ollama(monkeypatch, fail_first_n=0, entities=False)
    outcome = worker._extract_and_build_kg(_chunks(), "t1", "f.pdf")
    assert outcome is not None      # 零实体是**正常返回**，不是异常
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_worker_extraction_outcome.py -q --no-header`
Expected: FAIL（当前返回 tuple，无 `ExtractionOutcome`，全失败不抛）

- [ ] **Step 3: 实现 `ExtractionOutcome` 并改造 `_extract_and_build_kg`**

在 `worker.py` 顶层（`from errors import ...` 之后、`UPLOADS_DIR` 之前）加 dataclass 与 `dataclasses` import：

```python
from dataclasses import dataclass


@dataclass
class ExtractionOutcome:
    node_count: int
    edge_count: int
    batches_total: int
    batches_failed: int
    first_error: PipelineError | None = None

    @property
    def all_failed(self) -> bool:
        return self.batches_total > 0 and self.batches_failed == self.batches_total

    @property
    def partial(self) -> bool:
        return 0 < self.batches_failed < self.batches_total
```

然后用下面**完整**实现替换 `worker.py:829-909` 整个 `_extract_and_build_kg`（返回类型 `tuple[int, int]` → `ExtractionOutcome`）：

```python
def _extract_and_build_kg(chunks, task_id: str, filename: str) -> ExtractionOutcome:
    """用 Ollama qwen2.5:7b 对 chunks 做实体关系抽取，构建 KG。

    失败语义（显式，不再用 (0,0) 掩盖）：
      - 全部批次失败 → raise StageExtractionError（携带首个根因）
      - 部分批次失败 → 返回 batches_failed > 0 的 outcome，调用方标 degraded
      - 成功但零实体 → 返回 0/0 的 outcome，调用方记 EMPTY 提示
    """
    MAX_CHUNKS = 50
    BATCH_SIZE = 5
    OLLAMA_URL = "http://localhost:11434/api/chat"
    MODEL = "qwen2.5:7b"

    PROMPT = (
        "从以下文本中抽取安全生产领域的实体和关系。只输出合法JSON。"
        "实体类型: 制度, 机构, 人员, 行为, 设备, 场所, 标准, 其他。"
        "关系类型: 建立, 监管, 执行, 违反, 包含, 关联。"
        '输出格式: {"entities":[{"name":"实体名","type":"类型"}],'
        '"relations":[{"subject":"主体","predicate":"关系","object":"客体"}]}'
        "\n\n文本:\n"
    )

    sample = chunks[:MAX_CHUNKS]
    all_entities: dict[str, dict] = {}
    all_edges: list[dict] = []
    edge_set: set[tuple] = set()

    batches_total = 0
    batches_failed = 0
    first_error: PipelineError | None = None

    for i in range(0, len(sample), BATCH_SIZE):
        batch = sample[i:i + BATCH_SIZE]
        text = "\n\n".join(c.text for c in batch if hasattr(c, "text"))
        if not text.strip():
            continue

        batches_total += 1

        try:
            import requests
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL,
                      "messages": [{"role": "user", "content": PROMPT + text[:4000]}],
                      "format": "json", "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            result = json.loads(resp.json()["message"]["content"])
        except Exception as exc:
            # 改造前这里是 `except Exception: continue` —— 批次失败被静默跳过，
            # 调用方看到 (0,0) 会误判为"文档无实体"。现在显式计数并留根因。
            batches_failed += 1
            mapped = classify_external_error(
                exc, stage=PipelineStage.EXTRACTION, provider="ollama",
                task_id=task_id,
            )
            if first_error is None:
                first_error = mapped
            logger.warning(
                "extraction_batch_failed", task_id=task_id, batch_index=i,
                batch_size=len(batch), error_code=mapped.code.value,
                provider="ollama", exc_info=True,
            )
            continue

        for e in result.get("entities", []):
            name = e.get("name", "")
            if name and name not in all_entities:
                all_entities[name] = {
                    "node_id": f"n{len(all_entities)+1:05d}",
                    "label": name,
                    "entity_type": e.get("type", "其他"),
                    "grounding_status": "grounded",
                    "page_idx": 0,
                    "bbox_norm": None,
                }

        for r in result.get("relations", []):
            subj = r.get("subject", "")
            obj = r.get("object", "")
            pred = r.get("predicate", "关联")
            if subj and obj and subj in all_entities and obj in all_entities:
                key = (subj, obj, pred)
                if key not in edge_set:
                    edge_set.add(key)
                    all_edges.append({
                        "source_node_id": all_entities[subj]["node_id"],
                        "target_node_id": all_entities[obj]["node_id"],
                        "relation_type": pred,
                    })

    # 全部批次都失败 → 这是失败，不是"零实体"
    if batches_total and batches_failed == batches_total:
        raise StageExtractionError(
            "实体抽取全部批次失败",
            code=ErrorCode.PIPELINE_EXTRACTION_EMPTY,
            context=ErrorContext(
                provider="ollama", stage=PipelineStage.EXTRACTION,
                task_id=task_id, retryable=True,
                details={
                    "batches_total": batches_total,
                    "batches_failed": batches_failed,
                    "root_error": first_error.code.value if first_error else None,
                },
            ),
        ) from first_error

    if not all_entities:
        # 成功执行但确实没抽到实体 —— 正常返回，由调用方记 EMPTY 提示
        return ExtractionOutcome(0, 0, batches_total, batches_failed, first_error)

    kg_dir = os.path.join(os.path.dirname(__file__), "output", "kg", f"doc_{task_id}")
    os.makedirs(kg_dir, exist_ok=True)
    with open(os.path.join(kg_dir, "nodes.json"), "w", encoding="utf-8") as f:
        json.dump({"nodes": list(all_entities.values())}, f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(kg_dir, "edges.json"), "w", encoding="utf-8") as f:
        json.dump({"edges": all_edges}, f, ensure_ascii=False, indent=2)

    return ExtractionOutcome(len(all_entities), len(all_edges),
                             batches_total, batches_failed, first_error)
```

**注意**：原函数体内的 `import json as _json` 与局部别名 `_json` 一并去掉，统一用模块级 `json`（顶部已 import）。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_worker_extraction_outcome.py -q --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/worker.py backend/tests/test_worker_extraction_outcome.py
git commit -m "fix(worker): 抽取批次全失败不再伪装成零实体成功（正确性修复）"
```

---

## Task 8: `run_real_pipeline` 顶层 raise-through + 调用方接线（BEHAVIOR）

**Files:**
- Modify: `backend/worker.py:41-201, 711-826`
- Modify: `backend/routes/ingest.py:61-103`
- Modify: `backend/models.py:114-122`
- Create: `backend/tests/test_ingest_degraded_status.py`

**这是原子单元**：Task 7 的 outcome、本任务的 raise-through、以及 `routes/ingest.py` 的 `error_code` 接线互相依赖，任何子集都不自洽。

- [ ] **Step 1: `models.py` 加 `TaskResult.partial` / `warnings`**

```python
class TaskResult(BaseModel):
    ...
    partial: bool = False          # 新增，默认 False —— 向后兼容
    warnings: list[str] = []       # 新增，默认空
```

**不扩展 `TaskStatus`** —— 它是 wire 契约，且 DEGRADED 是质量维度而非生命周期状态。

- [ ] **Step 2: `worker.py` 用 `task_scope` 包裹并顶层 raise-through**

把现有 `run_real_pipeline` 正文改名 `_run_real_pipeline_inner`（纯改名，零行为变更），新增公开包装：

```python
def run_real_pipeline(task_id, filepath, filename, progress_callback, ingest_options=None):
    from logging_config import get_logger, task_scope
    log = get_logger(__name__)
    with task_scope(task_id):
        try:
            return _run_real_pipeline_inner(task_id, filepath, filename,
                                            progress_callback, ingest_options)
        except PipelineError as exc:
            log.error("pipeline_failed", task_id=task_id, error_code=exc.code.value,
                      stage=exc.stage.value if exc.stage else None, exc_info=True)
            progress_callback(
                exc.stage.value if exc.stage else "unknown",
                f"Pipeline Error ({exc.stage.value if exc.stage else 'unknown'})",
                0, {}, error=exc.message, error_code=exc.code.value,
            )
            raise       # 由 routes/ingest.py 决定任务终态
```

**Step 2a：改造 5 处 `progress_callback(..., error=...); return`**

改造前这些站点是「回调报错后 return None」，`routes/ingest.py:81-82` 把 `None` 解读为"已处理，直接返回"。改造后一律 raise，由 Step 2 的公开包装统一转成 `progress_callback(..., error_code=...)` 并继续向上抛。

`worker.py:64-104`（Path A 本地文件）整段替换为：

```python
        try:
            public_url = _upload_to_public(filepath)

            if public_url:
                progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "calling_api"})
                token = os.getenv("MINERU_API_TOKEN", "")
                # 改造后 _call_mineru_api 失败一律 raise（见 Task 6），
                # 因此不再需要 `if mineru_dir: ... else: ...return` 分支。
                mineru_dir = _call_mineru_api(public_url, token, task_id, ingest_options)
                progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
            else:
                # OSS 上传失败是**设计内**的降级路径（_upload_to_public 返回 None），
                # 回退到本地缓存，不是错误。
                progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "checking_cache"})
                output_mineru = os.path.join(os.path.dirname(__file__), "output", "mineru")
                if os.path.isdir(output_mineru):
                    for entry in sorted(os.listdir(output_mineru), reverse=True):
                        entry_path = os.path.join(output_mineru, entry)
                        if not os.path.isdir(entry_path):
                            continue
                        full_md_test = os.path.join(entry_path, "full.md")
                        cl_files_test = [
                            f for f in glob.glob(os.path.join(entry_path, "*_content_list.json"))
                            if "_v2" not in f
                        ]
                        if os.path.exists(full_md_test) and cl_files_test:
                            mineru_dir = entry_path
                            break

                if mineru_dir:
                    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
                else:
                    raise StageMinerUError(
                        "OSS 上传失败且无本地 MinerU 缓存",
                        code=ErrorCode.PIPELINE_MINERU_IO,
                        context=ErrorContext(
                            provider="oss", stage=PipelineStage.MINERU, task_id=task_id,
                            details={"hint": "检查 OSS 配置或改用 URL 模式上传"},
                        ),
                    )
        except PipelineError:
            raise
        except Exception as exc:
            raise StageMinerUError(
                "本地文件上传/解析失败",
                code=ErrorCode.PIPELINE_MINERU_UNKNOWN,
                context=ErrorContext(provider="oss", stage=PipelineStage.MINERU,
                                     task_id=task_id),
            ) from exc
```

`worker.py:105-117`（Path B URL 模式）替换为 —— 删除 `if not mineru_dir:` 死分支：

```python
    else:
        # ── Path B: URL mode - direct MinerU API call ──
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "running"})
        public_url = filepath
        token = os.getenv("MINERU_API_TOKEN", "")
        mineru_dir = _call_mineru_api(public_url, token, task_id, ingest_options)
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
```

`worker.py:133-135`（bridge）替换为：

```python
    except Exception as exc:
        raise StageBridgeError(
            "MinerU 输出解析/分段失败",
            code=ErrorCode.PIPELINE_BRIDGE_PARSE,
            context=ErrorContext(stage=PipelineStage.BRIDGE, task_id=task_id),
        ) from exc
```

`worker.py:147-149`（LangExtract）替换为：

```python
    except Exception as exc:
        raise StageExtractionError(
            "LangExtract 实体抽取失败",
            code=ErrorCode.PIPELINE_EXTRACTION_UNKNOWN,
            context=ErrorContext(provider="deepseek", stage=PipelineStage.EXTRACTION,
                                 task_id=task_id),
        ) from exc
```

`worker.py:157-159`（grounding）替换为：

```python
    except Exception as exc:
        raise StageGroundingError(
            "溯源解析失败",
            code=ErrorCode.PIPELINE_GROUNDING_ERROR,
            context=ErrorContext(stage=PipelineStage.GROUNDING, task_id=task_id),
        ) from exc
```

`worker.py:167-169`（KG build）替换为：

```python
    except Exception as exc:
        raise StageKGBuildError(
            "知识图谱构建或落盘失败",
            code=ErrorCode.PIPELINE_KG_BUILD_IO,
            context=ErrorContext(stage=PipelineStage.KG_BUILD, task_id=task_id),
        ) from exc
```

`worker.py:139-140`（runtime index 构建）**保持宽捕但不 raise** —— 它是尽力而为的旁路索引，失败只降级不阻断主流程。改为：

```python
    except Exception:
        # 运行时索引为旁路产物，构建失败只降级检索质量，不阻断入库主流程
        logger.warning("runtime_index_build_failed", task_id=task_id, exc_info=True)
```

- [ ] **Step 2b: `worker.py:786` 抽取调用改为消费 `ExtractionOutcome`**

```python
    outcome = _extract_and_build_kg(chunks, task_id, filename)
    kg_nodes, kg_edges = outcome.node_count, outcome.edge_count

    if outcome.partial:
        progress_callback(
            "extraction", "实体抽取与KG构建", 5,
            {"extraction": "degraded", "kg_nodes": kg_nodes, "kg_edges": kg_edges,
             "batches_failed": outcome.batches_failed,
             "batches_total": outcome.batches_total},
            error=f"{outcome.batches_failed}/{outcome.batches_total} 批次抽取失败，结果不完整",
            error_code=ErrorCode.PIPELINE_EXTRACTION_EMPTY.value,
            degraded=True,
        )
    elif kg_nodes == 0:
        progress_callback(
            "extraction", "实体抽取与KG构建", 5,
            {"extraction": "done", "kg_nodes": 0, "kg_edges": 0},
            error="未抽取到实体（文档可能非安全生产领域）",
            error_code=ErrorCode.PIPELINE_EXTRACTION_EMPTY.value,
            degraded=True,
        )
    else:
        progress_callback("extraction", "实体抽取与KG构建", 5,
                          {"extraction": "done", "kg_nodes": kg_nodes,
                           "kg_edges": kg_edges})
```

`StageExtractionError` **不在此处捕获** —— 让它冒泡到 Step 2 的公开包装，由那里统一转成任务终态。

同时把 `_run_real_pipeline_inner` 的返回 dict 补两个键（供 `routes/ingest.py` 的 `TaskResult` 消费）：

```python
        "partial": outcome.partial,
        "warnings": ([f"{outcome.batches_failed}/{outcome.batches_total} 批次抽取失败"]
                     if outcome.partial else []),
```

**注意**：`outcome` 变量需在 KG 落盘（`build_knowledge_graph`）之前就存在，且 Step 2b 的这段逻辑要放在原 `_extract_and_build_kg` 调用点（`worker.py:786` 附近），不要与 `kg_builder.build_knowledge_graph`（`worker.py:163`）混淆 —— 后者是 PDF 路径的 KG 构建，前者是 DOCX/XLSX 路径的 Ollama 抽取。两条路径都在同一函数内，改动时先确认自己在哪条分支。

- [ ] **Step 2c: 新增 `progress_callback` 的 `degraded` 契约**

`worker.py` 内所有 `progress_callback(...)` 调用在 `error_code` / `degraded` 上是鸭子类型调用 —— 回调签名由 `routes/ingest.py` 定义（见 Step 3）。`worker.py` 侧无需 import，但需保证传参名与 Step 3 的形参名一致（`error` / `error_code` / `degraded`）。

- [ ] **Step 3: `routes/ingest.py` 的 `progress()` 加 `error_code` / `degraded`**

```python
    def progress(stage_key, stage_name, step, details, error=None,
                 error_code=None, degraded=False):
        _tasks[task_id]["stage"] = stage_key
        _tasks[task_id]["progress"] = StageProgress(
            stage_name=stage_name, current_step=step, total_steps=5, details=details,
        ).model_dump()
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
        if error:
            if degraded:
                existing = _tasks[task_id].get("result") or {}
                _tasks[task_id]["result"] = {
                    **existing,
                    "partial": True,
                    "warnings": [*(existing.get("warnings") or []), error],
                }
                logger.warning("ingest_degraded", task_id=task_id, stage=stage_key,
                               error_code=error_code, detail=error)
            else:
                _tasks[task_id]["status"] = TaskStatus.FAILED
                _tasks[task_id]["error"] = TaskError(
                    code=error_code or ErrorCode.INTERNAL_ERROR.value,
                    message=error,
                ).model_dump()
                logger.error("ingest_failed", task_id=task_id, stage=stage_key,
                             error_code=error_code, detail=error)
        _save_tasks(_tasks)
```

同时：`routes/ingest.py:71` 的 `code="PIPELINE_ERROR"` 字面量随之消失（改为 `error_code` 参数传入）。`routes/ingest.py:121` 的 `traceback.print_exc()` 改为 `logger.error(..., exc_info=True)`。`routes/ingest.py` 需 import `get_logger` 与 `from errors import ErrorCode`。

`routes/ingest.py:77-79` 的 `except Exception as e:` → 保留但改为不丢 `error_code`：

```python
    except PipelineError as exc:
        progress(exc.stage.value if exc.stage else "mineru", "Pipeline Error", 0, {},
                 error=exc.message, error_code=exc.code.value)
        return
    except Exception as exc:
        logger.error("ingest_unexpected", task_id=task_id, exc_info=True)
        progress("mineru", "Pipeline Error", 0, {},
                 error=user_message(ErrorCode.INTERNAL_ERROR),
                 error_code=ErrorCode.INTERNAL_ERROR.value)
        return
```

- [ ] **Step 3b: `routes/ingest.py` 成功路径透传 `partial` / `warnings`**

把 `routes/ingest.py:92-100` 的 `TaskResult(...)` 构造补两个字段（`result` 是 `run_real_pipeline` 的返回值，改造后可能带 `partial`）：

```python
        "result": TaskResult(
            document_id=doc_id,
            kg_nodes=result["kg_nodes"],
            kg_edges=result["kg_edges"],
            grounded_entities=result["grounded_entities"],
            entity_types=result["entity_types"],
            pages_parsed=result["pages_parsed"],
            kg_path=result.get("kg_path", ""),
            partial=result.get("partial", False),           # 新增
            warnings=result.get("warnings", []),            # 新增
        ).model_dump(),
```

`run_real_pipeline` 需在自己的返回值里透传这两个键 —— 在 `_run_real_pipeline_inner` 组装返回 dict 处加：

```python
        "partial": outcome.partial if outcome else False,
        "warnings": ([f"{outcome.batches_failed}/{outcome.batches_total} 批次抽取失败"]
                     if outcome and outcome.partial else []),
```

- [ ] **Step 4: 写测试**

```python
"""任务终态语义：全失败 → failed；部分失败 → done + partial；零实体 → done + warning。

不跑真实 MinerU/Ollama —— 直接把 worker.run_real_pipeline 换成受控实现，
只验证 routes/ingest.py 的终态映射逻辑（这正是本次改造的核心）。
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (  # noqa: E402
    ErrorCode, ErrorContext, PipelineStage, StageExtractionError,
)


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=False)


def _run_ingest(client, monkeypatch, task_id, pipeline_impl):
    """把 task_id 注册进 routes.ingest._tasks 后直接调 _run_indexing。"""
    import routes.ingest as ing
    from worker import run_real_pipeline

    ing._tasks[task_id] = {
        "task_id": task_id,
        "status": ing.TaskStatus.PENDING,
        "filename": "t.docx",
        "file_size_bytes": 10,
        "created_at": ing.datetime.now(ing.timezone.utc),
        "updated_at": ing.datetime.now(ing.timezone.utc),
        "stage": None, "progress": None, "result": None, "error": None,
    }
    monkeypatch.setattr(ing, "_save_tasks", lambda *_: None)

    import worker
    monkeypatch.setattr(worker, "run_real_pipeline",
                        lambda *a, **k: pipeline_impl(*a, **k))

    ing._run_indexing(task_id, "uploads/t.docx", "t.docx", 10, {})
    return ing._tasks[task_id]


def _all_batches_failed(task_id, filepath, filename, progress, opts):
    exc = StageExtractionError(
        "实体抽取全部批次失败", code=ErrorCode.PIPELINE_EXTRACTION_EMPTY,
        context=ErrorContext(provider="ollama", stage=PipelineStage.EXTRACTION,
                             task_id=task_id),
    )
    raise exc


def _partial(task_id, filepath, filename, progress, opts):
    return {
        "document_id": "doc_partial", "kg_nodes": 3, "kg_edges": 2,
        "grounded_entities": 3, "entity_types": 1, "pages_parsed": 1,
        "kg_path": "", "partial": True, "warnings": ["1/2 批次抽取失败"],
    }


def _zero_entities(task_id, filepath, filename, progress, opts):
    return {
        "document_id": "doc_empty", "kg_nodes": 0, "kg_edges": 0,
        "grounded_entities": 0, "entity_types": 0, "pages_parsed": 1,
        "kg_path": "", "partial": False, "warnings": ["未抽取到实体"],
    }


def test_all_extraction_failed_marks_task_failed(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-fail", _all_batches_failed)
    assert task["status"] == "failed", f"实得 {task['status']}"
    assert task["error"]["code"] == "PIPELINE_EXTRACTION_EMPTY"
    # 用户可见文案不得是内部异常原文的裸拼接
    assert task["error"]["message"]


def test_partial_extraction_marks_partial(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-partial", _partial)
    assert task["status"] == "done"
    assert task["result"]["partial"] is True
    assert task["result"]["warnings"]


def test_zero_entities_is_done_with_warning(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-empty", _zero_entities)
    assert task["status"] == "done"
    assert task["result"]["partial"] is False
    assert task["result"]["warnings"]


def test_pipeline_error_literal_is_gone():
    """PIPELINE_ERROR 字面量必须全仓消失（backend + frontend）。"""
    repo = BACKEND.parent
    hits = []
    for p in list(BACKEND.rglob("*.py")) + list((repo / "frontend" / "src").rglob("*.ts*")):
        rel = str(p).replace("\\", "/")
        if ".venv" in rel or "/tests/" in rel or p.name == "test_ingest_degraded_status.py":
            continue
        if "PIPELINE_ERROR" in p.read_text(encoding="utf-8", errors="replace"):
            hits.append(rel)
    assert not hits, f"仍存在 PIPELINE_ERROR 字面量：{hits}"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_ingest_degraded_status.py -q --no-header`
Expected: PASS

- [ ] **Step 6: 确认既有测试未回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header`
Expected: 与 Task 0 基线一致（无新增失败）

- [ ] **Step 7: Commit**

```bash
git add backend/worker.py backend/routes/ingest.py backend/models.py backend/tests/test_ingest_degraded_status.py
git commit -m "fix(ingest): 任务降级态可区分，PIPELINE_ERROR 字面量收敛为分层错误码"
```

---

## Task 9: 路由不再泄露内部异常文本（BEHAVIOR，SECURITY）

**Files:**
- Modify: `backend/routes/query.py:244-245`, `backend/routes/bot.py:126-127`, `backend/routes/export.py:22-35`
- Create: `backend/tests/test_route_error_boundary.py`

**范围说明**：只迁移这 3 处。其余 `HTTPException(detail=f"...")` 站点（`routes/ingest.py`、`routes/graph.py`、`routes/bot.py:84,128`）插值的是用户提交值或非敏感值（URL、扩展名、字节数、task_id、平台名），不是泄露。全仓扫一遍是徒增回归面的 churn。

- [ ] **Step 1: 写失败测试（用哨兵字符串断言不外泄）**

```python
"""路由异常不得把内部异常文本回显到响应体。

哨兵字符串法：让被测分支抛出一条含 SENTINEL 的异常，然后断言
响应体中**找不到** SENTINEL —— 比断言"等于某固定文案"更耐改。
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SENTINEL = "INTERNAL-SECRET-SENTINEL-abcdef123456"


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=False)


def test_query_route_does_not_leak_exception_text(client, monkeypatch):
    """routes/query.py 捕获 Agent 异常后不得回显其文本。

    改造前此处是 HTTPException(500, detail=f"Agent error: {str(e)}")，SENTINEL 会原样出现在响应体。

    注意：本测试**只**断言不外泄，不断言 error.code —— 异常处理器要到 Task 10
    才注册，此刻 UpstreamUnavailableError 仍走 FastAPI 默认 500。错误码形状由
    tests/test_exception_handlers.py 覆盖。
    """
    import routes.query as q

    def _boom(*args, **kwargs):
        raise RuntimeError(f"upstream exploded: {SENTINEL}")

    monkeypatch.setattr(q, "_get_agent", lambda: object())
    monkeypatch.setattr(q, "_invoke_legacy_agent", _boom)

    r = client.post("/api/v1/query", json={"query": "测试问题"})
    assert SENTINEL not in r.text, f"响应体泄露了内部异常文本：{r.text[:300]}"
    assert r.status_code >= 400


def test_bot_route_does_not_leak_exception_text(client, monkeypatch):
    """routes/bot.py 的飞书连接测试失败不得回显异常文本。"""
    import routes.bot as b

    class _BoomClient:
        configured = True

        def _get_tenant_token(self):
            raise RuntimeError(f"feishu auth failed: {SENTINEL}")

    monkeypatch.setattr(b, "FeishuClient", _BoomClient)

    r = client.post("/api/v1/bot/config/feishu/test")
    assert SENTINEL not in r.text, f"响应体泄露了内部异常文本：{r.text[:300]}"
    assert r.status_code >= 400


def test_export_route_rejects_with_safe_message(client):
    """非法 format 被 Pydantic Query(pattern=...) 拦在边界，不进入业务逻辑。

    此处用真实请求验证边界校验生效即可 —— 断言不出现 traceback / 内部类名。
    """
    r = client.get("/api/v1/export/kg", params={"format": "definitely-not-a-format"})
    assert r.status_code == 422
    assert "Traceback" not in r.text
    assert "exporter" not in r.text.lower()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_route_error_boundary.py -q --no-header`
Expected: FAIL（响应体含 SENTINEL）

- [ ] **Step 3: 三处改造**

`routes/query.py:242-245`（当前 `raise HTTPException(500, detail=f"Agent error: {str(e)}")`）改为：

```python
    try:
        result = _invoke_legacy_agent(agent, req.query, language=req.options.language)
    except Exception as e:
        raise UpstreamUnavailableError(
            "KG 查询 Agent 调用失败",
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            context=ErrorContext(provider="deepseek", retryable=True),
        ) from e
```

`routes/bot.py:126-127`（当前 `raise HTTPException(status_code=500, detail=f"Feishu connection failed: {e}")`）改为：

```python
        except Exception as e:
            raise UpstreamUnavailableError(
                "飞书连接测试失败",
                code=ErrorCode.UPSTREAM_UNAVAILABLE,
                context=ErrorContext(provider="feishu"),
            ) from e
```

`routes/export.py:22-23` 与 `:34-35` —— **注意这两处当前已经是 `except ValueError`（已收窄），不是宽捕**。因此**不要**加 `# noqa: BLE001`（Task 16 启用了 `RUF100`，未使用的 noqa 会让 CI 失败）。本处只需补 `from e` 以保留异常链，满足 F004 的 `raise ... from` 要求：

```python
    except ValueError as e:
        # 导出器的 ValueError 只描述用户提交的 format 参数，消息可安全外露
        raise HTTPException(status_code=400, detail=str(e)) from e
```

两处（`:22-23` 与 `:34-35`）都照此改。

`routes/query.py` 与 `routes/bot.py` 需在文件顶部补 import：

```python
from errors import ErrorCode, ErrorContext, UpstreamUnavailableError
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_route_error_boundary.py -q --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/query.py backend/routes/bot.py backend/routes/export.py backend/tests/test_route_error_boundary.py
git commit -m "security(routes): 停止将内部异常文本回显到响应体"
```

---

## Task 10: 注册结构化异常边界（BEHAVIOR，契约变更）

**Files:**
- Modify: `backend/errors.py`（加 `register_exception_handlers`）
- Modify: `backend/server.py:343-345` 之前
- Create: `backend/tests/test_exception_handlers.py`

**契约变更**：错误响应形状由 `{"detail": "..."}` 变为 `{"error": {"code", "message"}, "detail": "<message>"}`（双写兼容期）。

- [ ] **Step 1: 写失败测试**

```python
"""异常边界：状态码映射 + error/detail 双写 + 不回显用户输入。

通过临时挂载探针路由来触发各错误码 —— 比构造真实上游失败更稳，
且能覆盖到没有对应业务端点的错误码。
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from pydantic import BaseModel

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (  # noqa: E402
    ErrorCode, ErrorContext, PipelineError, StageMinerUError,
    UpstreamUnavailableError, register_exception_handlers,
)

SENTINEL = "INTERNAL-SECRET-SENTINEL-abcdef123456"


@pytest.fixture
def probe_app():
    """最小 app，只注册错误边界 + 探针路由。"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/pipeline/{code}")
    async def boom(code: str):
        raise StageMinerUError("上游阶段失败", code=ErrorCode(code))

    @app.get("/boom/upstream")
    async def boom_upstream():
        raise UpstreamUnavailableError("上游不可用")

    @app.get("/boom/unhandled")
    async def boom_unhandled():
        raise RuntimeError(f"kaboom {SENTINEL}")

    # ⚠️ 必须用真实的 Pydantic 模型，不能用 `payload: dict` ——
    # FastAPI 会把整个 body 直接绑给 dict，**校验永不触发**，
    # 于是 test_validation_error_* 两个测试会一个 200（失败）、
    # 另一个空转通过。实测踩到：原稿用 dict 时校验处理器完全没被执行。
    class EchoPayload(BaseModel):
        password: str
        n: int

    @app.post("/echo")
    async def echo(payload: EchoPayload):
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


# ── 状态码映射（含 INTERNAL_ERROR 不得被误映射成 502 的回归守卫）──
@pytest.mark.parametrize("code,expected", [
    ("PIPELINE_MINERU_AUTH", 401),
    ("PIPELINE_MINERU_RATE_LIMIT", 429),
    ("PIPELINE_MINERU_TIMEOUT", 502),
    ("PIPELINE_MINERU_SERVER", 502),
    ("PIPELINE_MINERU_PARSE", 502),
    ("PIPELINE_MINERU_ERROR", 502),
    ("PIPELINE_EXTRACTION_EMPTY", 502),
])
def test_pipeline_error_maps_to_status(probe_app, code, expected):
    r = probe_app.get(f"/boom/pipeline/{code}")
    assert r.status_code == expected, f"{code} 期望 {expected}，实得 {r.status_code}"


def test_upstream_unavailable_maps_to_503(probe_app):
    assert probe_app.get("/boom/upstream").status_code == 503


def test_internal_error_maps_to_500_not_502(probe_app):
    """回归守卫：INTERNAL_ERROR 字面以 '_ERROR' 结尾，
    若 _http_status_for 不先判它，会被误映射成 502。"""
    r = probe_app.get("/boom/unhandled")
    assert r.status_code == 500, f"实得 {r.status_code}"


# ── 响应形状：error + detail 双写 ──
def test_response_has_error_and_detail(probe_app):
    r = probe_app.get("/boom/pipeline/PIPELINE_MINERU_AUTH")
    body = r.json()
    assert body["error"]["code"] == "PIPELINE_MINERU_AUTH"
    assert body["error"]["message"]          # 用户可读文案非空
    assert body["detail"] == body["error"]["message"]   # 兼容期双写


def test_catch_all_does_not_leak_exception_text(probe_app):
    """哨兵字符串不得出现在响应体。"""
    r = probe_app.get("/boom/unhandled")
    assert SENTINEL not in r.text
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"


def test_validation_error_does_not_echo_submitted_input(probe_app):
    """Pydantic 的 RequestValidationError.errors() 带 'input' 键，
    会把用户提交的原值（登录时是密码）回显进响应与日志 —— 必须剥离。"""
    r = probe_app.post("/echo", json={"password": SENTINEL, "n": "not-an-int"})
    assert r.status_code == 422
    assert SENTINEL not in r.text, "校验错误响应回显了用户提交的原值"
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_validation_error_strips_input_key(probe_app):
    r = probe_app.post("/echo", json={"password": SENTINEL, "n": "not-an-int"})
    assert "input" not in r.text


def test_every_pipeline_code_has_a_default_message(probe_app):
    """任何 PipelineError 都必须能渲染出用户可读文案，不能露出裸码。"""
    for code in ("PIPELINE_GROUNDING_ERROR", "PIPELINE_KG_BUILD_ERROR",
                 "PIPELINE_PARSE_ERROR", "PIPELINE_BRIDGE_ERROR"):
        r = probe_app.get(f"/boom/pipeline/{code}")
        msg = r.json()["error"]["message"]
        assert msg and msg != code, f"{code} 无文案，回显了裸码"
```

- [ ] **Step 2: 实现 `register_exception_handlers`**

在 `errors.py` 追加（FastAPI import 放函数内，保持模块 stdlib-only 的**真相**不变 —— 注意：`register_exception_handlers` 内部 import FastAPI 会污染模块级 `sys.modules`，因此 Task 1 的 stdlib-only 测试是**在子进程里**跑 `import errors`，不受影响；但更干净的做法是本函数体在**首次调用时**才 import）。

```python
def register_exception_handlers(app) -> None:
    """注册流水线错误边界。必须在 include_router 之前调用。"""
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from logging_config import get_logger, get_request_id
    from models import ErrorResponse, TaskError

    @app.exception_handler(PipelineError)
    async def _pipeline_error_handler(request: Request, exc: PipelineError) -> JSONResponse:
        get_logger("errors").error(
            "pipeline_error", error_code=exc.code.value,
            stage=exc.stage.value if exc.stage else None,
            provider=exc.context.provider, http_status=exc.context.http_status,
            provider_code=exc.context.provider_code, task_id=exc.context.task_id,
            retryable=exc.context.retryable, request_id=get_request_id(),
            path=request.url.path,
            exc_info=exc.__cause__ or exc,       # 原始 traceback 只进日志
        )
        payload = ErrorResponse(error=TaskError(code=exc.code.value,
                                                message=user_message(exc.code)))
        content = payload.model_dump()
        content["detail"] = payload.error.message      # 兼容期双写
        return JSONResponse(status_code=_http_status_for(exc.code), content=content)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        get_logger("errors").info(
            "request_validation_failed", path=request.url.path,
            errors=[{"loc": e.get("loc"), "msg": e.get("msg")} for e in errors[:5]],
        )
        payload = ErrorResponse(error=TaskError(
            code=ErrorCode.VALIDATION_ERROR.value,
            message=_format_validation_errors(errors),
        ))
        content = payload.model_dump()
        content["detail"] = payload.error.message
        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(Exception)
    async def _catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
        get_logger("errors").error("unhandled_exception", path=request.url.path,
                                   exc_type=type(exc).__name__, exc_info=True)
        payload = ErrorResponse(error=TaskError(
            code=ErrorCode.INTERNAL_ERROR.value,
            message=user_message(ErrorCode.INTERNAL_ERROR),
        ))
        content = payload.model_dump()
        content["detail"] = payload.error.message
        return JSONResponse(status_code=500, content=content)


def _http_status_for(code: ErrorCode) -> int:
    v = code.value
    # 注意：这几个必须**先**判，否则会掉进下面的 endswith("_ERROR") 分支。
    # 特别是 INTERNAL_ERROR —— 它字面以 "_ERROR" 结尾，若不先判会被误映射成 502。
    if v == ErrorCode.VALIDATION_ERROR.value:
        return 422
    if v == ErrorCode.UPSTREAM_UNAVAILABLE.value:
        return 503
    if v == ErrorCode.INTERNAL_ERROR.value:
        return 500
    if v.endswith("_AUTH"):
        return 401
    if v.endswith("_RATE_LIMIT"):
        return 429
    # 其余 PIPELINE_* 阶段失败 → Bad Gateway（上游/流水线阶段失败，不是本服务 500）
    if v.endswith(("_SERVER", "_TIMEOUT", "_IO", "_PARSE", "_EMPTY", "_UNKNOWN", "_ERROR")):
        return 502
    return 500


def _format_validation_errors(raw) -> str:
    """Pydantic 错误摘要。必须剥离 input/ctx —— 否则用户 POST 的整个 body
    （登录时是密码、建 Webhook 时是密钥）会回显进响应与日志。"""
    parts = []
    for item in raw[:5]:
        loc = ".".join(str(x) for x in item.get("loc", ()))
        parts.append(f"{loc}: {item.get('msg', 'invalid')}")
    return "; ".join(parts) or "请求参数校验失败"
```

- [ ] **Step 3: 在 `server.py` 注册（`include_router` 之前）**

在 `server.py:343`（`# ── Routes ──` 注释）之前插入：

```python
# 结构化异常边界 —— 必须在 include_router 之前注册
from errors import register_exception_handlers
register_exception_handlers(app)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_exception_handlers.py -q --no-header`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header`
Expected: 与基线一致。**若既有测试断言 `{"detail": ...}` 的旧形状**，在同一提交内更新为断言双写形状（`detail` 仍在，所以大多不受影响）。

- [ ] **Step 6: Commit**

```bash
git add backend/errors.py backend/server.py backend/tests/test_exception_handlers.py
git commit -m "feat(errors): 注册结构化异常边界（error+detail 双写兼容）"
```

---

## Task 11: 修复唯一的裸 except

**Files:**
- Modify: `backend/routes/query.py:277-278`

- [ ] **Step 1: 收窄**

```python
                except (json.JSONDecodeError, TypeError, KeyError):
                    # 响应体非 JSON / 结构不符时跳过该来源提取，不影响主答案
                    logger.debug("source_extraction_skipped", exc_info=True)
```

- [ ] **Step 2: 验证清零**

Run: `cd backend && grep -rnE "except\s*:" --include="*.py" . | grep -v "\.venv" | grep -v "/tests/"`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add backend/routes/query.py
git commit -m "fix(routes): 消除全仓唯一一处裸 except"
```

---

## Task 12: 库代码 28 处 `print()` 收敛

**Files:**
- Modify: `backend/kg_builder.py` (19), `backend/worker.py` (4 + 3 `traceback.print_exc()`), `backend/oss_uploader.py` (2), `backend/embedding.py` (2), `backend/doc_processor.py` (1)

**范围**：CLI 脚本（`pipeline.py` / `run_evaluation.py` / `agentic_rag_mvp.py` / `build_indices.py` / `scripts/check_imports.py`，共 109 处）**保持不变**，在 Task 16 的 ruff `per-file-ignores` 中显式豁免。

- [ ] **Step 1: 逐文件替换为 structlog**

**已确认的 28 处位置（逐处可核对，勿凭印象）**：

| 文件 | 行号 | 现内容 |
|---|---|---|
| `kg_builder.py` | 134, 173, 198, 223, 248, 272, 297 | `print(f"[kg_builder] Warning: <relation> target ... not found for source {n.node_id}")` |
| `kg_builder.py` | 342 | `print(f"[kg_builder] Warning: missing key in edge data: {key} for edge {e}")` |
| `kg_builder.py` | 380, 381, 382, 383, 384, 394, 396, 398, 405, 407, 409 | `print_kg_summary` 的汇总表（12 条 print） |
| `oss_uploader.py` | 52, 57 | `print(f"[OSS] 上传文件: ...")` / `print(f"[OSS] 上传成功: {url}")` |
| `embedding.py` | 93, 95 | `print(f"[embedding] Loading model: ...")` / `Loading done` |
| `doc_processor.py` | 927 | `print(f"[doc_processor] Skipping {fname}: {e}")` |
| `worker.py` | 753, 778, 790, 933 | `traceback.print_exc()`（**不是** `print(...)`，同样违规） |
| `routes/ingest.py` | 121 | `traceback.print_exc()` |

先把 7 处 Warning 收敛为一条带 `logger.warning` 的调用。`kg_builder.py` 目前**没有** logger，先加：

```python
from collections import Counter, defaultdict

from logging_config import get_logger

logger = get_logger(__name__)
```

每处 Warning 的替换形状（以 `:134` 为例，其余 6 处同理，只换 `relation` 名与变量名）：

```python
# 改造前
            print(f"[kg_builder] Warning: reports_to target '{reports_to_val}' not found in nodes for source {n.node_id}")
# 改造后
            logger.warning("kg_relation_target_missing",
                           relation="reports_to", target=reports_to_val,
                           source_node_id=n.node_id)
```

`:342` 的 `missing key` 同形（`logger.warning("kg_edge_key_missing", key=key, edge=e)`）。

**`print_kg_summary` 的签名必须保持不变** —— `pipeline.py:50` import 它、`:330` 调用它（`print_kg_summary(nodes, edges)`），而 `pipeline.py` 是 Task 16 豁免的 CLI 文件，如果改名或加必填参数，`pipeline.py` 立刻 ImportError。因此**保留函数名与签名**，只把函数体从 12 条 print 换成 1 条结构化日志：

```python
def print_kg_summary(nodes: list[KGNode], edges: list[KGEdge]):
    """记录 KG 汇总。函数名保持向后兼容（pipeline.py 仍以该名 import）。

    历史名带 print_ 前缀，但输出走 structlog —— 这正是 Task 16 对 CLI 脚本
    豁免 T20 的原因：CLI 的可读 stdout 由各自的 print 提供，本函数服务于
    库路径（worker.py），不应污染 stdout。
    """
    logger.info(
        "kg_summary",
        nodes=len(nodes),
        edges=len(edges),
        entity_types=dict(Counter(n.entity_type for n in nodes)),
        relation_types=dict(Counter(e.relation_type for e in edges)),
        grounded=sum(1 for n in nodes if getattr(n, "grounding_status", None) == "grounded"),
    )
```

**注意**：这里用 `n.entity_type` / `e.relation_type` 属性访问（`nodes` 是 `list[KGNode]`，`edges` 是 `list[KGEdge]`），**不是** dict 下标 —— 原 `print_kg_summary` 的 `nodes` 参数是 list 不是 dict。若实现时发现调用方传的是 dict，需按实际类型调整。

`worker.py:753, 778, 790, 933` 与 `routes/ingest.py:121` 的 `traceback.print_exc()` → `logger.error("<event>", exc_info=True)`（事件名按上下文取，如 `"mineru_output_gone"` / `"oss_upload_failed"`）。

`oss_uploader.py:52, 57` → `logger.info("oss_uploading", path=..., object_name=...)` / `logger.info("oss_upload_ok", url=url)`。
`embedding.py:93, 95` → `logger.info("embedding_model_loading", model=self.model)` / `logger.info("embedding_model_loaded", dim=self.dim)`。

⚠️ **`embedding.py` 并没有现成的 logger** —— 计划初稿误称"该文件已用 structlog"，实测为 `NameError: name 'logger' is not defined`（被 `tests/test_runtime_caching.py::test_embedding_model_is_cached_process_wide` 抓到）。与 `kg_builder.py` 一样需先加 `from logging_config import get_logger` + `logger = get_logger(__name__)`。
`doc_processor.py:927` → `logger.warning("doc_skipped", filename=fname, error=str(e), exc_info=True)`。

- [ ] **Step 2: 验证 5 个库文件清零**

Run:
```bash
cd backend && for f in kg_builder.py worker.py oss_uploader.py embedding.py doc_processor.py; do
  n=$(grep -c "print(" "$f" || true); echo "$f: $n"
done
```
Expected: 全部 `0`

- [ ] **Step 2b: 验证 CLI 仍可运行（改名/改签名会在这里暴露）**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "
import ast, sys
src = open('pipeline.py', encoding='utf-8').read()
ast.parse(src)
from kg_builder import print_kg_summary
print('pipeline 的 import 仍成立')
"
```
Expected: `pipeline 的 import 仍成立`

- [ ] **Step 3: 确认 CLI 脚本仍保有 print（豁免是承重的）**

Run: `cd backend && grep -c "print(" pipeline.py run_evaluation.py agentic_rag_mvp.py build_indices.py scripts/check_imports.py`
Expected: 分别 36 / 34 / 24 / 11 / 4

- [ ] **Step 4: 回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header`

- [ ] **Step 5: Commit**

```bash
git add backend/kg_builder.py backend/worker.py backend/oss_uploader.py backend/embedding.py backend/doc_processor.py
git commit -m "refactor(logging): 库代码 28 处 print 收敛为 structlog（CLI 入口保留）"
```

---

## Task 13: 5 个 stdlib-logging 遗留模块统一到 structlog

**Files:**
- Modify: `backend/retrieval.py:34`, `backend/worker.py:27`, `backend/routes/health.py:8`, `backend/routes/rag_query.py:26`, `backend/routes/graph.py:7`

**为什么必须做**：这 5 个模块用 `logging.getLogger(__name__)` 会**绕过** Task 3 的脱敏处理器。其中 `worker.py` 正是本次修复的核心模块，其日志若不脱敏则整个改造留下缺口。

- [ ] **Step 1: 替换 logger 构造**

`logging.getLogger(__name__)` → `get_logger(__name__)`，并加 `from logging_config import get_logger`。

注意 `logging_config.py` 同时配置了 stdlib root（`:76-80`）且用 `structlog.stdlib.LoggerFactory`，所以输出格式对调用方行为保持兼容；但 `%s` 风格的位置参数需改为 structlog 的 kwargs 形态（`logger.warning("msg %s", x)` → `logger.warning("msg", x=x)`），逐处检查。

- [ ] **Step 2: 验证**

Run: `cd backend && grep -rn "logging.getLogger" --include="*.py" . | grep -v "\.venv"`
Expected: 仅剩 `logging_config.py` 自身的 `logging.getLogger(__name__)`（那是配置器，应当保留）

- [ ] **Step 3: 回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header`

- [ ] **Step 4: Commit**

```bash
git add backend/retrieval.py backend/worker.py backend/routes/health.py backend/routes/rag_query.py backend/routes/graph.py
git commit -m "refactor(logging): 5 个模块的 stdlib logging 统一到 structlog（修复脱敏链缺口）"
```

---

## Task 14: 静默吞异常点标注豁免（纯标注，不改控制流）

**Files:**
- Modify: **114 处静默吞站点，分布于 32 个文件**（实际执行后经 AST 实测确认；计划初稿写 116 是把一个已被 Task 6/7/8/11 改造掉的站点也算进去了）

实测分布（`# noqa` 尚未加时的基线，按站点数降序）：

| 站点数 | 文件 |
|---|---|
| 14 | `services/catalog.py` |
| 8 | `services/lifecycle.py` |
| 7 | `services/quality.py` |
| 6 | `services/backup.py`、`services/feedback_store.py`、`services/kg_exporter.py` |
| 5 | `server.py`、`worker.py` |
| 4 | `index_registry.py`、`kg_store.py`、`services/api_key_manager.py`、`services/lineage_store.py`、`services/tenant_service.py`、`routes/documents.py`、`routes/health.py`、`routes/rag_query.py` |
| 3 | `retrieval.py`、`services/auth_service.py` |
| 2 | `conversation.py`、`generator.py`、`table_index.py`、`services/event_bus.py`、`services/kg_service.py`、`services/webhook_manager.py`、`routes/query.py` |
| 1 | `kg_builder.py`、`services/audit_logger.py`、`routes/auth.py`、`routes/bot.py`、`routes/ingest.py`、`middleware/jwt_middleware.py`、`middleware/tenant_middleware.py` |

这 114 处**不含** Task 6/7/8/11 已改造的站点（那些已改为显式处理，不再静默）。**先跑 Step 2 的脚本拿到真实数字，再逐处标注** —— 若数字与上表不符，以脚本输出为准。

`commit` 时按实际改动的文件逐个 `git add`，**不要用 `git add -A`** —— 工作区还有 300+ 未跟踪文件（见背景事实）。

**明确禁止**：不重写 `services/catalog.py` / `lifecycle.py` / `quality.py` / `backup.py` 的聚合逻辑。这些地方的 catch-all 是合理设计（统计降级不应中断主流程），只加标注。

- [ ] **Step 1: 逐处补 `# noqa: BLE001  # <理由>`**

格式（理由必须存在且具体）：

```python
    try:
        get_event_bus().publish("doc.ingested", {...})
    except Exception:  # noqa: BLE001  # 事件总线失败不得中断入库主流程（fire-and-forget）
        pass
```

**理由必须说明"为什么宽捕是正确的"**，而不是复述代码。按站点性质选用下表中的理由 —— 同文件同类站点用同一句：

| 站点性质 | 理由模板 |
|---|---|
| 聚合统计降级（`services/catalog.py` 等） | `# 统计聚合降级：单维读取失败不应让整个目录接口失败` |
| 后台投递 fire-and-forget（`services/event_bus.py`、`webhook_manager.py`） | `# 后台投递失败不阻塞主请求（fire-and-forget，见 CLAUDE.md Webhook 规则）` |
| 可选依赖/文件缺失 | `# 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定` |
| 清理/回滚尽力而为（`services/lifecycle.py`） | `# 清理为尽力而为，失败已记入返回的 errors 列表，不中断其余类别` |
| 缓存读写失败（`conversation.py`、`retrieval.py`） | `# 缓存读写失败可容忍：命中率下降但结果正确` |
| Windows 文件锁容忍（`logging_config.py` 的 rollover） | `# Windows 轮转目标被占用时跳过本次轮转，不终止进程` |
| 兼容旧格式/脏数据（`index_registry.py`、`kg_store.py`） | `# 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录` |

**不含控制流的改动**：本任务只允许在 `except` 行尾追加注释，禁止改动 `except` 的类型、`pass`/`continue`/`return` 的语义、或块的边界。审阅时可用 `git diff -w` 确认只有注释行变化。

- [ ] **Step 2: 确认没有遗漏**

Run:
```bash
cd backend && .venv/Scripts/python.exe - <<'PY'
import ast, pathlib
SKIP = {".venv", "output", "__pycache__", "uploads", "node_modules"}
root = pathlib.Path(".")
missing = []
stack = [root]
while stack:
    d = stack.pop()
    for e in d.iterdir():
        if e.is_dir():
            if e.name in SKIP or e.name.startswith("."):
                continue
            stack.append(e)
            continue
        if e.suffix != ".py":
            continue
        s = str(e).replace("\\", "/")
        if s.startswith("tests/"):
            continue
        lines = e.read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                missing.append(f"{s}:{node.lineno} 裸 except")
                continue
            if getattr(node.type, "id", "") != "Exception":
                continue
            silent = all(
                isinstance(b, (ast.Pass, ast.Continue))
                or (isinstance(b, ast.Return) and b.value is None)
                for b in node.body
            )
            if silent and "# noqa" not in lines[node.lineno - 1]:
                missing.append(f"{s}:{node.lineno} 静默吞且无 noqa")
print("\n".join(missing) if missing else "OK: 全部已标注")
PY
```
Expected: `OK: 全部已标注`

- [ ] **Step 3: 回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --no-header`

- [ ] **Step 4: Commit**

```bash
git add -A backend/services backend/routes backend/index_registry.py backend/generator.py backend/kg_store.py backend/conversation.py backend/server.py
git commit -m "chore(errors): 为合理的宽捕站点标注豁免理由（控制流不变）"
```

---

## Task 15: 策略守卫测试（ruff 开启前的预检）

**Files:**
- Create: `backend/tests/test_error_handling_policy.py`

**作用**：在 Task 16 开启 ruff 之前，先证明代码真的干净。若本任务不能全绿，说明 Task 12-14 有遗漏，**不要**进入 Task 16。

- [ ] **Step 1: 写守卫测试**

```python
"""错误处理策略守卫 —— ruff 开启前的预检，同时防止后续回流。"""
import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CLI_T20_EXEMPT = {
    "pipeline.py", "run_evaluation.py", "agentic_rag_mvp.py",
    "build_indices.py", "scripts/check_imports.py",
}
# 被跳过的目录。注意 .venv 下有近 2 万个 .py —— 必须**在遍历时剪枝**，
# 而不是 rglob 出来再过滤（后者每个测试多走 2 万次 stat）。
_SKIP_DIRS = {".venv", "output", "__pycache__", "uploads", "node_modules", ".pytest-tmp"}


def _sources():
    """yield (Path, rel_posix) —— 只含 backend 自身的库/路由代码，不含 tests。"""
    stack = [BACKEND]
    while stack:
        d = stack.pop()
        for entry in d.iterdir():
            if entry.is_dir():
                if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                    continue
                stack.append(entry)
            elif entry.suffix == ".py":
                rel = str(entry.relative_to(BACKEND)).replace("\\", "/")
                if rel.startswith("tests/"):
                    continue
                yield entry, rel


def test_library_modules_have_no_print():
    """库代码 print 清零；5 个 CLI 脚本是显式豁免。"""
    offenders = []
    for path, rel in _sources():
        if rel in CLI_T20_EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"库代码仍有 print()：{offenders}"


def test_cli_exemptions_are_load_bearing():
    """豁免清单不得变成垃圾桶：列出的文件必须真的含 print。"""
    for rel in CLI_T20_EXEMPT:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert "print(" in src, f"{rel} 已无 print，应从豁免清单移除"


def test_no_bare_except_outside_tests():
    offenders = []
    for path, rel in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"存在裸 except：{offenders}"


def test_every_ble001_noqa_has_a_reason():
    """每条 # noqa: BLE001 必须带 `#` 理由，否则豁免无从审计。"""
    offenders = []
    for path, rel in _sources():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if "noqa" not in line or "BLE001" not in line:
                continue
            if line.split("BLE001", 1)[1].count("#") < 2:
                offenders.append(f"{rel}:{lineno}")
    assert not offenders, f"# noqa: BLE001 缺少理由：{offenders}"


def test_worker_uses_structlog():
    """worker.py 必须走 structlog，否则绕过脱敏链。"""
    src = (BACKEND / "worker.py").read_text(encoding="utf-8")
    assert "logging.getLogger" not in src
    assert "get_logger" in src
```

- [ ] **Step 2: 运行，确认全绿**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_error_handling_policy.py -q --no-header`
Expected: PASS（若失败 → 回到 Task 12/13/14 补齐，**不要**进入 Task 16）

- [ ] **Step 3: 验证守卫非空转（关键）**

临时在 `retrieval.py` 里加 `print("x")`，重跑 `test_library_modules_have_no_print` → 必须 FAIL；撤销。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_error_handling_policy.py
git commit -m "test(errors): 新增错误处理策略守卫（print/noqa/裸 except）"
```

---

## Task 16: 开启 ruff 规则（ENFORCEMENT）

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `.github/workflows/ci.yml:22-25`

- [ ] **Step 1: dev 依赖加 ruff，钉住 CI 版本**

`pyproject.toml` 的 `[dependency-groups].dev` 加 `"ruff>=0.8.0"`。CI 的 `chartboost/ruff-action@v1` **未钉版本**，配置行为会随解析版本漂移 —— 改为显式钉版本的调用。

- [ ] **Step 2: 写 `[tool.ruff]` 配置**

```toml
# ── Ruff ────────────────────────────────────────────────────────────────
# 规则来源：.claude/rules/error-handling.md
#   E722 裸 except / BLE001 盲捕 / S110 try-except-pass / T20 业务代码禁 print
# 落地顺序：先清代码（Task 1-15），最后开规则（本任务），否则 CI 中途必红。

[tool.ruff]
target-version = "py312"
line-length = 120
src = ["."]
extend-exclude = [".venv", "output", "__pycache__", "uploads"]

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",   # E7 含 E722 裸 except
    "F",                # pyflakes
    "BLE",              # BLE001 blind except
    "S110",             # try-except-pass
    "T20",              # T201 print
    "RUF100",           # 未使用的 noqa
]
# 明确不启用（防后续无意识扩张）：
#   S 全量 —— 与 bandit SAST 重复且噪声大，只挑 S110 精确命中
#   T 全量 —— 只启用 T20 子集

[tool.ruff.lint.per-file-ignores]
# T20：这 5 个是可独立运行的 CLI 入口，其 stdout 就是用户界面。
# 用 per-file-ignores 而非逐行 # noqa：豁免是**文件角色**属性，
# 109 行逐行 noqa 只会训练审阅者忽略 noqa。
"pipeline.py" = ["T20"]
"run_evaluation.py" = ["T20"]
"agentic_rag_mvp.py" = ["T20"]
"build_indices.py" = ["T20"]
"scripts/check_imports.py" = ["T20"]   # stdout 是 CI 步骤的可见输出（ci.yml 冒烟步骤）
# 测试：用 except Exception 做容错断言、用 print 调试属正常实践
"tests/**" = ["T20", "BLE001", "S110", "E722"]
```

**豁免纪律**：语句级豁免用行内 `# noqa: BLE001  # 理由`；文件角色级豁免才用 `per-file-ignores`。二者都必须是**承重的、可枚举的**，不得成为垃圾桶 —— 由 Task 15 的 `test_cli_exemptions_are_load_bearing` 强制。

- [ ] **Step 3: 本地验证非空转**

Run:
```bash
cd backend && uv tool run ruff==0.8.4 check . ; echo "exit=$?"
```
Expected: `exit=0`。然后临时在 `retrieval.py` 加 `print("x")` → `uv tool run ruff==0.8.4 check .` 必须报 T201；撤销。

- [ ] **Step 4: 确认规则的命中面符合预期**

Run: `cd backend && uv tool run ruff==0.8.4 check . --statistics`
Expected: 全部为 0；若有非零项，说明 Task 12-14 有遗漏（S110 与 BLE001 对 `except: pass` 会重复报告，属正常）。

- [ ] **Step 5: 改 CI lint job**

现有 lint job 用 `chartboost/ruff-action@v1`（**未钉版本**，且不保证传 `--config`，配置行为会随解析版本漂移）。改为与 `dependency-audit` job 同一套写法（`astral-sh/setup-uv@v5` + `uv tool run` + 逐 job 设 `UV_DEFAULT_INDEX`）：

```yaml
  lint:
    runs-on: ubuntu-latest
    env:
      # 锁文件绑定阿里云；uv tool run 拉取 ruff 本身也走此镜像（见 backend/CLAUDE.md 镜像约束）
      UV_DEFAULT_INDEX: https://mirrors.aliyun.com/pypi/simple/
    steps:
      - uses: actions/checkout@v4

      - name: Setup uv
        uses: astral-sh/setup-uv@v5

      - name: Ruff (Python lint)
        working-directory: ./backend
        run: |
          # 钉版本：@v1 action 未钉，规则行为会随解析版本漂移
          # 读 backend/pyproject.toml 的 [tool.ruff]（工作目录已切到 backend）
          uv tool run ruff==0.8.4 check .

      # ... 下面 Node / ESLint 步骤保持原样
```

（原 job 里 Node/ESLint 部分不动，只替换 ruff 那一步并补 setup-uv。）

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock .github/workflows/ci.yml
git commit -m "ci(lint): 开启 ruff 错误处理规则并钉住版本"
```

---

## Task 17: bandit SAST job（ENFORCEMENT，补 F002 遗留 AC）

**Files:**
- Modify: `backend/pyproject.toml`（加 `[tool.bandit]`）
- Modify: `.github/workflows/ci.yml`
- Create: `docs/governance/sast-exemptions-2026-09-18.md`

- [ ] **Step 1: 写 `[tool.bandit]`**

```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv", "output", "uploads", "__pycache__"]
```

**豁免不放 `skips`** —— 放在 CI 调用点的注释里。理由：审阅者是在 CI 日志里看到失败时去读 CI 文件，而不是去翻 toml。

- [ ] **Step 2: 本地先跑一遍，盘点发现**

Run: `cd backend && uv tool run bandit==1.7.10 -c pyproject.toml -r . -ll -ii`
Expected: 输出待评估项。**已知会有** `worker.py` 的 `subprocess.run(["curl", ...])` 触发 B603/B607。

**评估结论（须写入台账）**：`worker.py:957/977/1003-1004` 的 argv 是**静态列表**、无 `shell=True`、插值项为 `base`（来自 env）、`mineru_task_id` 与 `zip_url`（均来自 MinerU 响应），不接受用户直传的 shell 元字符。**这是已评估接受的发现，不是未处理项。**

- [ ] **Step 3: 写台账 `docs/governance/sast-exemptions-2026-09-18.md`**

沿用 `docs/governance/dependency-audit-2026-09-17.md` 的体例：每条豁免一行，含规则 ID、全部命中 `file:line`、可利用性判断、无法修复的原因、**复查触发条件**。

- [ ] **Step 4: 写 CI job**

插在 `dependency-audit` job 之后：

```yaml
  bandit-sast:
    runs-on: ubuntu-latest
    env:
      UV_DEFAULT_INDEX: https://mirrors.aliyun.com/pypi/simple/
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: bandit（中危+中置信度起阻断）
        working-directory: ./backend
        run: |
          # -ll -ii = 中危+中置信度起。默认 -l -i 会报大量低危噪声，
          # 结果是阻塞 CI 或被迫整体跳过 —— 二者都会训练人忽略该 job。
          #
          # 豁免项（每条须在 docs/governance/sast-exemptions-2026-09-18.md 落档）：
          #   B603/B607 subprocess —— worker.py 的 curl 调用，argv 为静态列表、
          #     无 shell=True、插值项来自 env 与 MinerU 响应。已评估接受。
          uv tool run bandit==1.7.10 -c pyproject.toml -r . -ll -ii
```

- [ ] **Step 5: 验证非空转**

临时在 scratch 文件写 `import hashlib; hashlib.md5(b"x")` → bandit 必须报 B324；撤销。

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml .github/workflows/ci.yml docs/governance/sast-exemptions-2026-09-18.md
git commit -m "ci(sast): 新增 bandit 静态扫描 job 与豁免台账"
```

---

## Task 18: 文档与 LRA 回流（铁律 7）

**Files:**
- Modify: `.claude/rules/error-handling.md`
- Modify: `backend/CLAUDE.md`
- Modify: `.lra/feature-list.json`
- Modify: `.lra/progress.txt`

- [ ] **Step 1: 更新 `.claude/rules/error-handling.md` 的基线数字**

该文件开头写着「本项目当前问题：229 处 `except Exception`/裸 `except`，133 处 `print()`」。改为改造后的实际值。**铁律 7 要求代码与规范一致** —— 留着旧数字就是新的漂移。

- [ ] **Step 2: `backend/CLAUDE.md` 补日志规则**

在「日志规则」小节补充：`task_id`/`job_phase` 语义（`job_phase="background"` 时 `request_id` 是**入队请求**的 id）、脱敏处理器行为（`[REDACTED]` 的含义与深度/宽度边界）、错误码命名规范（`PIPELINE_<STAGE>_<REASON>`）。

- [ ] **Step 3: 更新 `.lra/feature-list.json`**

F003 / F004 置 `"status": "completed"`，填 `completed_at` 与 `notes`（记录实际改动量与偏差）。

- [ ] **Step 4: 追加 `.lra/progress.txt` Session 2**

记录：执行方式、分支、计划路径、完成项、实现中发现的计划外问题、给下个 session 的 Notes。

- [ ] **Step 5: Commit**

```bash
git add .claude/rules/error-handling.md backend/CLAUDE.md .lra/feature-list.json .lra/progress.txt
git commit -m "docs(governance): 错误处理基线回流 + F003/F004 完成标记"
```

---

## 收尾项（不在本次执行，记录以免遗忘）

- [x] **缓存回退降为显式 opt-in —— 已完成（2026-09-18）**。`_find_cached_mineru_output` 只按目录名字典序取一个目录、与待入库文件无关（实测 6 个目录时恒定返回 `ingest_f`）。本次 refactor 让第③级从"罕见可达"变成"网络抖动即触发"，会把**别的文档**的产物当成本次入库。处置：默认**不参与**，需显式传 `allow_cached_mineru_output=true`；启用时记 `mineru_using_cached_output` 告警（含 note 说明缓存与本次文件无关）。已加 2 个测试（默认不用 / 显式才用），并变异验证：把默认改成开启 → `test_cache_is_NOT_used_by_default` 立即失败。
- [ ] **`kg_builder.py` 关系查找失败后继续用失败值**（Task 16 执行中发现，经用户决定另开任务）。8 处 `logger.warning(...)` 之后**控制流继续**，使用本该由失败查找产出的值，同时把节点状态写成 `"ungrounded"` —— 抽取失败会**静默产出形状不同的 KG 节点**，且失败的边被丢弃而调用方无从得知。**先写复现测试**证明是「边被静默丢弃」还是「建成错节点」，有证据后再定修法（标 ungrounded 后 continue 跳过 vs raise 由上层处理）。原位置约在 134/173/198/223/248/272/297/342（行号已变，须重新定位）。
- [ ] **`table_index.py:237` 的 B608 SQL 拼接**：WHERE 子句由 LLM 产出的 `table_conditions` 直接拼接。正确解法是把 `table_conditions` 从自由文本改为结构化条件对象（列名白名单 + 运算符枚举 + 参数化值），需同步改 `retrieval.py` 的抽取 prompt 与 `index_registry.query` 签名。已豁免并落档 `docs/governance/sast-exemptions-2026-09-18.md`（含 4 条复查触发条件）。
- [ ] **`ruff` 的 `--select` + `--fix` 陷阱**：`--select` 会**覆盖**配置的 select，使其他规则显示为 non-enabled，ruff 随即删除它们的 `# noqa`。本次因此误删 114 条标注（已恢复）。**若将来有自动化脚本包装 ruff，须禁止 `--select` 与 `--fix` 同用。**
- [ ] **两份测试模块的假 structlog stub 仍未移除**：`test_community_global_mode.py` / `test_kg_indexed_recall.py` 的模块级 `SimpleNamespace` 现由 conftest 的真 `import structlog` 压住。属可工作但脆弱的安排 —— 彻底做法是让那两个模块用自己的 stub 而非污染 `sys.modules`。
- [ ] **向量化/索引失败是否应升级为硬失败？** 见下条独立任务。
- [ ] **前端改读 `error.code` 后，删除 Task 10 的 `detail` 兼容双写字段。** 触发条件：`frontend/src/lib/api.ts` 改为读 `response.error.code`。删除前需确认 Engine-Vue 侧（`D:\puzzlegame\Engine-Vue-master`）的错误解析路径 —— 该问题**需人工确认**，不要自行判断。
- [x] **端到端验证 Task 8 的核心修复 —— 已完成（2026-09-18）**。DOCX 入库在 **Ollama 停止**时报 `failed` + `PIPELINE_EXTRACTION_EMPTY`（实测）；Ollama 恢复后同一文件正常入库（`done`、`kg_nodes=72`、`partial=False`）。两个方向都验证过。
  - **关键发现**：DOCX 走 `_run_local_parse_pipeline`，在 MinerU 分支**之前**返回 —— 完全不经过 MinerU/OSS，所以这个测试**不需要任何外部凭据**，一直可跑（此前误以为要等 MinerU Token）。
  - **复现要点**：停 Ollama 用 `taskkill /F /IM "ollama app.exe"` + `ollama.exe`；重启必须起 **`ollama app.exe`（桌面版）**，**不能**只起 `ollama serve` —— 后者的模型目录是空的，`/api/tags` 返回空列表、推理报 `model not found`，会让结果失真（曾因此误判成"正向也失败"）。
- [ ] `docker-compose.yml` 的 chromadb 服务与代码（用 `PersistentClient`）不一致 —— 独立任务。
- [ ] **凭据轮换**：① git 历史中的旧 DeepSeek key（`docs/governance/security-incident-2026-09-17-tracked-credentials.md`）；② `.claude/settings.local.json` 含真实 `LANGEXTRACT_API_KEY` 与 `SPRING_DATASOURCE_PASSWORD`（该文件未被跟踪、受全局 gitignore 保护，未入库，但明文在磁盘）。均需人工操作。
- [ ] **`harness-engineering` / `langextract` 的 gitlink 悬空**：index 中 mode 160000 但无 `.gitmodules`，指针漂移（对应 backlog F010）。
- [ ] `backend/.venv` 缺 `pytest-timeout`，`pyproject.toml:62` 的 `timeout=60` 不生效 —— 独立小任务。

---

## 执行顺序的硬约束

1. **Task 1 必须最先** —— Task 6-11 全部 import `errors.py`。
2. **Task 15 必须先于 Task 16**。若 Task 16 落地后 CI 变红，说明顺序被破坏，而这正是排序要避免的。
3. **Task 10 必须在 Task 9 之后**。否则 3 处 `detail=str(e)` 在过渡期会与新的 PipelineError 路径产出不一致形状。
4. **Task 6/7/8 必须原子落地**。MinerU 的 raise、抽取的 outcome、`error_code` 的接线互相依赖，任何子集都不自洽。
5. **`worker.py` 上的 Task 6/7/8/12/13 必须串行**。同一文件的改动，不可并行派发。
6. **Task 5 执行前先跑 `git check-ignore -v output/logs/app.log`**。退出码非 0 则停止并升级。
7. **Task 8 合并前需人工端到端验证**：① 一份真实 PDF 走通 MinerU；② 一份 DOCX 在 **Ollama 停止**的情况下入库，确认 `GET /status/{task_id}` 报 `failed` + `PIPELINE_EXTRACTION_EMPTY`。第 ② 条正是本次修复的缺陷，没有观察到这个红→绿，修复即未经验证。

---

## 验收对照（F003 / F004 AC）

| AC | 落地任务 | 验证方式 |
|---|---|---|
| F003: 非测试 print 清零（或仅 CLI 保留） | Task 12 + 16 | `test_library_modules_have_no_print` + ruff T20 |
| F003: 统一 structlog + JSON | Task 3, 12, 13 | `test_worker_uses_structlog`；`get_logger` 全覆盖 |
| F003: 日志携带 request_id / task_id / trace_id | Task 2 | `task_scope` 落 `task_id`+`job_phase`；`test_log_redaction` 的 benign 断言保证 `task_id` 不被误脱敏 |
| F003: 日志脱敏 | Task 3, 4, 5 | `test_log_redaction` 语料 + 反向断言；`PurgeScript` 幂等 |
| F004: 禁裸 except / 禁静默 pass | Task 11, 14, 16 | ruff E722 + `test_no_bare_except_outside_tests`；`# noqa: BLE001 # 理由` 全覆盖 |
| F004: 五阶段分层错误码 | Task 1, 8 | `test_errors.py`；`models.py:124 TaskError.code` 喂枚举值 |
| F004: 外部调用区分 401/429/5xx/超时 | Task 1, 6, 7 | `test_worker_mineru_errors` / `test_worker_extraction_outcome` |
| F004: 顶层边界 `raise ... from` | Task 6, 7, 8 | 每处 `raise ... from exc`；`test_exception_handlers` 断言不回显内部文本 |
