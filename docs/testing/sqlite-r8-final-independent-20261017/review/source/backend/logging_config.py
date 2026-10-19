"""
Structured logging configuration — §3.1 of enterprise-evolution-blueprint.

JSON Lines → stdout + TimedRotatingFileHandler → output/logs/app.log
Every request gets a UUID4 request_id via contextvars for full-link tracing.
"""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Mapping

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
task_id_var: ContextVar[str] = ContextVar("task_id", default="")


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Windows-friendly rotating file handler that tolerates locked rollover targets."""

    def doRollover(self) -> None:  # stdlib 覆写点，方法名由 logging 决定
        try:
            super().doRollover()
        except PermissionError:
            logging.getLogger(__name__).warning(
                "log_rollover_skipped",
                extra={"reason": "permission_denied"},
            )



def _ensure_log_dir(log_dir: str = "output/logs") -> Path:
    p = Path(log_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def setup_logging(log_dir: str = "output/logs") -> None:
    """Configure structlog with JSON stdout + rotating file output."""
    handlers: list[logging.Handler] = []

    # Console handler is always available as the safe fallback.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(console_handler)

    try:
        log_path = _ensure_log_dir(log_dir)
        handler_factory = (
            SafeTimedRotatingFileHandler
            if isinstance(TimedRotatingFileHandler, type)
            else TimedRotatingFileHandler
        )
        file_handler = handler_factory(
            filename=str(log_path / "app.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001  # 文件日志句柄创建失败时降级为仅 stdout 输出，不阻断服务启动
        file_handler = None
    else:
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(message)s")  # raw JSON, no double-encoding
        )
        handlers.insert(0, file_handler)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)

    # structlog — JSON renderer, bound context
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


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog logger bound to the given name."""
    return structlog.get_logger(name)


def set_request_id() -> str:
    """Generate and bind a new request_id. Called by middleware."""
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    structlog.contextvars.bind_contextvars(request_id=rid)
    return rid


def get_request_id() -> str:
    """Return current request_id or empty string."""
    return request_id_var.get()


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

# ⚠️ **顺序敏感**：`_scrub_scalar` 命中**第一个**匹配的模式就返回，后面的不再试。
# 因此**宽模式必须排在窄模式之前** —— 否则窄模式先命中、只替换它那一小段，
# 宽模式想覆盖的其余敏感部分会漏出去。
# 实例：预签名 URL 里同时含 `OSSAccessKeyId=LTAI...` 与 `Signature=...`。
# LTAI 规则（窄）若排在预签名 URL 规则（宽）之前，就只抹掉 AccessKeyId，
# **签名值完好泄出** —— 2026-09-18 实测踩到这个。
_SENSITIVE_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 预签名 URL（**宽模式，必须最前**）：签名在 query string 里，键名规则抓不到
    # （键叫 upload_url / file_url，不含 token/key/signature 段），只有值扫描能拦。
    # 签名即凭据（过期前可写该对象）；命中即整条 URL 替换 —— URL 不是诊断必需字段
    # （要排障记 host + batch_id 即可，见 mineru_client.apply_upload_urls 的日志写法）。
    re.compile(
        r"https?://\S*[?&](?:X-Amz-Signature|Signature|OSSAccessKeyId|"
        r"X-Amz-Credential|X-Amz-Security-Token)=[^&\s]+",
        re.IGNORECASE,
    ),
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
