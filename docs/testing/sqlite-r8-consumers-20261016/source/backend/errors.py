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

_PROVIDER_CODE_MAP: dict[str, dict[Any, FailureReason]] = {
    # MinerU 有**两套**失败形态，实测确认（2026-09-18）：
    #
    #   ① HTTP 状态码非 2xx —— 401/422/429/5xx。
    #      响应体**没有 `code` 字段**，用**字符串** msgCode，例如：
    #          HTTP 401 {"msgCode":"A0202","msg":"user authenticate failed","success":false}
    #      （该例由一次过期 Token 触发。）所以从 body 读 code 拿不到鉴权信息，
    #      必须靠 HTTP 状态码 —— 这就是 worker.py 需要 `curl -w "%{http_code}"` 的原因。
    #
    #   ② HTTP 200 + 负数 body `code` —— **业务**失败。已实测到的：
    #
    # 历史教训：本表最初填的是 -10001 / -60001..-60004 等码，**那些数字是编造的** ——
    # 规格文档（langextract/docs/MinerU-API-Specification.md §4.5）与真实响应都不支持，
    # 它们只存在于当时的代码/测试/计划里，导致测试"通过"却与真实契约不符。
    # 本次改为**只收录实测观察到、并记录触发条件的码**；未观察到的宁可不填
    # （会退化为 UNKNOWN，比填错更安全）。
    "mineru": {
        # 实测：提交一个被区域限制的 URL 时返回
        #   HTTP 200 {"code":-60023,"msg":"this URL is restricted by regional regulations and cannot be accessed"}
        # 语义是"这个 URL 取不到"，重试原样请求无用 → 非可重试，归类为 IO。
        # 复查触发条件：若 MinerU 更新该码含义，或遇到其它负数码，须实测后补录。
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

def _is_provider_timeout(exc: BaseException) -> bool:
    # 保留既有按类名兼容；通过继承链识别 requests.Timeout 和 httpx 的
    # Pool/WriteTimeout 等子类，同时保持本模块不导入第三方依赖。
    return type(exc).__name__ in ("TimeoutException", "ReadTimeout", "ConnectTimeout") or any(
        base.__module__.split(".", 1)[0] in {"requests", "httpx"}
        and base.__name__ in {"Timeout", "TimeoutException"}
        for base in type(exc).__mro__
    )

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
      2. 异常类型 → 超时 / 响应不可解析
      3. 异常携带的 HTTP 状态码 → 401/403=AUTH, 429=RATE_LIMIT, 5xx=SERVER
      4. 通用连接异常（在 requests 的 OSError 子类具体分类之后）
      5. 兜底 UNKNOWN
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

    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)) or _is_provider_timeout(exc):
        return err_cls(
            f"{provider} 请求超时",
            code=_compose(stage, FailureReason.TIMEOUT),
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
        elif status in (400, 422):
            reason, msg = FailureReason.PARSE, f"{provider} 拒绝了请求参数 ({status})"
        else:
            reason, msg = FailureReason.UNKNOWN, f"{provider} 返回异常状态 {status}"
        return err_cls(
            msg, code=_compose(stage, reason),
            context=ErrorContext(provider=provider, http_status=status, stage=stage,
                                 task_id=task_id,
                                 retryable=reason in (FailureReason.RATE_LIMIT,
                                                      FailureReason.SERVER)),
        )

    if isinstance(exc, (ConnectionError, OSError)) or _is_httpx_connect_error(exc):
        return err_cls(
            f"{provider} 无法连接",
            code=_compose(stage, FailureReason.SERVER),
            context=ErrorContext(provider=provider, stage=stage, task_id=task_id,
                                 retryable=True),
        )

    return err_cls(
        f"{provider} 调用失败",
        code=_compose(stage, FailureReason.UNKNOWN),
        context=ErrorContext(provider=provider, stage=stage, task_id=task_id),
    )

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


def register_exception_handlers(app) -> None:
    """注册流水线错误边界。必须在 include_router 之前调用。

    FastAPI / models 的 import 刻意放在函数体内：errors.py 顶层必须保持
    stdlib-only（见 tests/test_errors.py::test_errors_module_is_stdlib_only），
    而 models.py 会 import config → 读环境变量。
    """
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
