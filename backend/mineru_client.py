"""MinerU HTTP 传输层 —— 提交、上传、轮询、下载。

职责边界：本模块**只**负责与 MinerU 的 HTTP 交互，不知道 bridge / KG / 任务状态。
流水线编排留在 `worker.py`。

两条提交路径（2026-09-18 实测确认服务端有这两个端点）：
  ① TASK  —— `POST /api/v4/extract/task`，传一个**公网 URL**。
             适用：输入本身就是 URL；或本地文件先传到别处拿到 URL（OSS 回退路径）。
  ② BATCH —— `POST /api/v4/file-urls/batch` 申请预签名上传 URL → `PUT` 直传文件。
             适用：**本地文件**（默认路径），无需自建对象存储。

**两套端点的响应形状不同，这是本模块存在的主要理由**：
  TASK  轮询 → `data.state` / `data.full_zip_url`
  BATCH 轮询 → `data.extract_result[0].state` / `.full_zip_url`
用 `_POLL_PATH` 这张表把差异收敛成数据，而不是在轮询逻辑里分叉。

注意：MinerU 官方规格文档（langextract/docs/MinerU-API-Specification.md §1.3）
说"云端 API 不支持直接上传文件"—— **该说法已过时**，实测 `/file-urls/batch`
返回 200 并给出可用的预签名 URL。
"""

from __future__ import annotations

import enum
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from errors import (
    ErrorCode, ErrorContext, PipelineError, PipelineStage,
    StageMinerUError, classify_external_error,
)
from logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_API_BASE = "https://mineru.net/api/v4/extract/task"

# 轮询上限。刻意与 worker.py 保持同一硬编码值（不读 MINERU_MAX_WAIT_SECONDS /
# MINERU_POLL_INTERVAL）—— 本次是内部重构，不改变既有超时行为。
# 那两个环境变量在 .env.example 里声明但代码从未读取，属已知的潜伏不一致，
# 另开任务处理，不在本次范围内。
_MAX_POLLS = 120
_POLL_INTERVAL_SECONDS = 5
_MAX_UPLOAD_ATTEMPTS = 2


class MineruRoute(str, enum.Enum):
    """提交路径。决定轮询端点与响应解析方式。"""

    TASK = "task"      # POST /extract/task            → 轮询 /extract/task/{id}
    BATCH = "batch"    # POST /file-urls/batch         → 轮询 /extract-results/batch/{id}


@dataclass(frozen=True)
class MineruHandle:
    """已提交作业的不透明句柄。

    `route` 决定去哪儿轮询、怎么解析；`job_id` 是端点路径参数
    （TASK 用 mineru task_id，BATCH 用 batch_id）。
    """

    route: MineruRoute
    job_id: str


@dataclass(frozen=True)
class LocalFileUpload:
    """`POST /file-urls/batch` 的返回：预签名上传上下文。

    ⚠️ `upload_url` 内嵌签名，**是凭据** —— 禁止整串写进日志。
    只记 `batch_id` / `filename` / host（见 apply_upload_urls 的日志写法）。
    现有的 `redact_sensitive` 处理器**拦不住**它（签名在 query string 里，
    键名规则不含 url 段），所以靠调用点自律。
    """

    batch_id: str
    upload_url: str
    filename: str


class _HttpStatusError(Exception):
    """携带 HTTP 状态码的轻量异常。

    用途：`curl` 子进程拿不到 requests/httpx 的响应对象，而
    `classify_external_error` 靠 duck-type 读 `.response.status_code` / `.status`
    来判定 401/429/5xx。本类把状态码包装成它认得的形态，避免为 curl 路径
    另开一套分类分支。
    """

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.status = status_code          # oss2 形态的兼容别名
        super().__init__(f"HTTP {status_code}{(': ' + detail) if detail else ''}")


def _http_status_error(status_code: int, body: object = None) -> _HttpStatusError:
    """从 MinerU 错误响应体里取可读信息，构造带状态码的异常。"""
    detail = ""
    if isinstance(body, dict):
        detail = str(body.get("msg") or body.get("msgCode") or "")
    return _HttpStatusError(status_code, detail)


def _split_curl_status(stdout: str) -> tuple[int | None, object]:
    """解析 `curl -s -w "\\n%{http_code}"` 的输出，返回 (状态码, 解析后的 JSON body)。

    为什么必须这么绕：`curl -s` 默认只输出响应体，**丢弃 HTTP 状态码**，
    于是 401 这类「状态码有意义、响应体里没有 code 字段」的失败会被误当成
    业务错误或解析错误（2026-09-18 用真实过期 Token 实测确认）。加
    `-w "\\n%{http_code}"` 让状态码成为输出的最后一行。

    **body 不可解析时不能在丢掉状态码的情况下抛错** —— 401 完全可能带 HTML
    错误页。因此：有状态码则返回 (状态码, {})，让调用方按状态码分类；
    无状态码才抛 json.JSONDecodeError（由调用方转成 PARSE 分类）。
    200 + 不可解析 body 会走到 `data["data"]["task_id"]` 的 KeyError → PARSE，
    结果同样正确。
    """
    lines = stdout.rsplit("\n", 1)
    http_status: int | None = None
    body_text = stdout
    if len(lines) == 2:
        try:
            http_status = int(lines[1].strip())
            body_text = lines[0]
        except ValueError:
            pass          # 末行不是状态码，整体按 body 处理

    try:
        return http_status, json.loads(body_text)
    except json.JSONDecodeError:
        if http_status is not None:
            return http_status, {}
        raise


def _api_root(api_base: str | None = None) -> str:
    """从配置的 task 端点推出 API 根，供拼 batch 端点用。

    `MINERU_API_BASE_URL` 历史上指的就是 `.../api/v4/extract/task` 这个完整
    端点（.env 与 .env.example 均如此），而 batch 两个端点是它的**兄弟路径**
    （`/file-urls/batch`、`/extract-results/batch/{id}`）。与其新增一个配置项
    造成"两处都能改"的割裂，不如在这里把基址归一化 —— 剥掉已知的端点后缀。
    """
    base = (api_base or os.getenv("MINERU_API_BASE_URL") or DEFAULT_API_BASE).rstrip("/")
    for suffix in ("/extract/task", "/file-urls/batch", "/extract-results/batch"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def _curl_json(url: str, *, token: str, task_id: str, timeout: int = 30,
               method: str = "GET", body: str | None = None) -> tuple[int | None, object]:
    """发一次 JSON 请求，返回 (HTTP 状态码, 解析后的 body)。

    统一走 `curl -s -w "\\n%{http_code}"` —— 见 `_split_curl_status` 的说明。
    transport 层失败（超时/非 JSON）转成 PipelineError 后再抛，调用方无需
    再包一层 try。
    """
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "--max-time", str(timeout), "-X", method, url]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", body]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc
    except Exception as exc:  # 进程边界：子进程可能以任意方式失败，一律交给 classify_external_error 分级
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc

    try:
        return _split_curl_status(result.stdout)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc


def _raise_for_status(http_status: int | None, payload: object, *, task_id: str) -> None:
    """非 2xx 一律按状态码分类抛错（401→AUTH / 429→RATE_LIMIT / 5xx→SERVER）。"""
    if http_status is not None and not (200 <= http_status < 300):
        raise classify_external_error(
            _http_status_error(http_status, payload),
            stage=PipelineStage.MINERU, provider="mineru", task_id=task_id,
        )


def apply_upload_urls(
    token: str, *, filename: str, task_id: str,
    ingest_options: dict | None = None, api_base: str | None = None,
) -> LocalFileUpload:
    """申请一对一批次的预签名上传 URL。

    ⚠️ 返回的 URL 有时效（签名内含 Expires）。调用方应**立即** PUT，
    不要缓存后再用 —— 重试须重新申请（见 `submit_local_file`）。
    """
    opts = ingest_options or {}
    payload = json.dumps({
        "enable_formula": bool(opts.get("enable_formula", True)),
        "language": opts.get("language", "ch"),
        "model_version": opts.get("model_version", "pipeline"),
        "files": [{"name": filename, "is_ocr": bool(opts.get("is_ocr", True))}],
    })

    http_status, data = _curl_json(
        f"{_api_root(api_base)}/file-urls/batch",
        token=token, task_id=task_id, method="POST", body=payload,
    )
    _raise_for_status(http_status, data, task_id=task_id)

    if not isinstance(data, dict) or data.get("code") not in (None, 0):
        raise classify_external_error(
            RuntimeError("mineru apply upload url failed"),
            stage=PipelineStage.MINERU, provider="mineru",
            body_code=(data or {}).get("code") if isinstance(data, dict) else None,
            task_id=task_id,
        )

    try:
        batch_id = data["data"]["batch_id"]
        upload_url = data["data"]["file_urls"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise StageMinerUError(
            "MinerU 未返回可用的上传地址",
            code=ErrorCode.PIPELINE_MINERU_PARSE,
            context=ErrorContext(
                provider="mineru", stage=PipelineStage.MINERU,
                task_id=task_id, retryable=False,
            ),
        ) from exc

    # 只记非敏感字段 —— upload_url 内嵌签名，禁止整串入日志。
    logger.info("mineru_upload_url_applied", task_id=task_id,
                batch_id=batch_id, filename=filename)
    return LocalFileUpload(batch_id=batch_id, upload_url=upload_url, filename=filename)


def put_file(upload: LocalFileUpload, local_path: str, *, task_id: str) -> None:
    """PUT 本地文件到预签名 URL。

    **不带 Authorization 头** —— 签名已在 URL 里。带上反而可能被 OSS 拒绝。
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "-w", "\n%{http_code}", "--max-time", "600",
             "-o", os.devnull, "-X", "PUT", "--upload-file", local_path, upload.upload_url],
            capture_output=True, text=True, timeout=620,
        )
    except subprocess.TimeoutExpired as exc:
        raise StageMinerUError(
            "上传文档到 MinerU 超时",
            code=ErrorCode.PIPELINE_MINERU_IO,
            context=ErrorContext(provider="mineru", stage=PipelineStage.MINERU,
                                 task_id=task_id, retryable=True),
        ) from exc
    except Exception as exc:  # 进程边界：子进程可能以任意方式失败，一律交给 classify_external_error 分级
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc

    http_status, _ = _split_curl_status_safe(result.stdout)
    if http_status is not None and not (200 <= http_status < 300):
        # ⚠️ 必须经 classify_external_error 包装，**不能直接 raise _http_status_error(...)**。
        # 原因：`_HttpStatusError` 继承 `Exception` 而非 `PipelineError`，直接抛会穿透
        #   - `submit_local_file` 的 `except PipelineError`（重试逻辑失效）
        #   - `_resolve_mineru_dir` 的 `except PipelineError`（OSS / 缓存回退失效）
        # 最终落到 routes/ingest.py 的兜底 `except Exception`，用户只看到
        # "服务器内部错误"。预签名 URL 过期正是会走这条路径的**常见**失败
        # （403），也就是重试机制本来要处理的那种 —— 曾因此让重试与整个
        # 降级链在最需要时静默失效。
        raise classify_external_error(
            _http_status_error(http_status), stage=PipelineStage.MINERU,
            provider="mineru", task_id=task_id,
        )

    logger.info("mineru_upload_ok", task_id=task_id,
                batch_id=upload.batch_id, http_status=http_status)


def _split_curl_status_safe(stdout: str) -> tuple[int | None, object]:
    """`_split_curl_status` 的容错版：PUT 的响应体通常为空，不是 JSON。

    空 body 对 `_curl_json` 是错误（期望 JSON），但对 PUT 是**正常**的，
    所以这里单独处理：解析不出 JSON 时退化为 (状态码, None)。
    """
    try:
        return _split_curl_status(stdout)
    except json.JSONDecodeError:
        return None, None


def submit_local_file(
    token: str, *, local_path: str, filename: str, task_id: str,
    ingest_options: dict | None = None, api_base: str | None = None,
) -> MineruHandle:
    """本地文件直传的**唯一入口**：申请 URL → 上传 → 返回批次句柄。

    把 apply 与 put 的时序与时序耦合收在本函数内，使调用方拿不到
    "已申请但未上传"的中间态 —— 预签名 URL 有时效，中间态是危险的。

    重试**重新申请 URL**：URL 一次性且有 Expires，重放同一个 URL 会在
    过期后得到 403，而该 403 在本层无法与"因其它原因被拒"区分。
    只重试 retryable 失败（IO/超时/限流/5xx）；AUTH / PARSE 立即上抛 ——
    重试修不好坏 token，白白耗掉 OSS 回退的机会。
    """
    last_error: PipelineError | None = None
    for attempt in range(_MAX_UPLOAD_ATTEMPTS):
        try:
            upload = apply_upload_urls(
                token, filename=filename, task_id=task_id,
                ingest_options=ingest_options, api_base=api_base,
            )
            put_file(upload, local_path, task_id=task_id)
            return MineruHandle(route=MineruRoute.BATCH, job_id=upload.batch_id)
        except PipelineError as exc:
            if not exc.context.retryable:
                raise
            last_error = exc
            logger.warning("mineru_upload_retry", task_id=task_id,
                           attempt=attempt + 1, error_code=exc.code.value,
                           exc_info=True)
    raise last_error  # type: ignore[misc]


# 两套轮询响应的下钻路径：(key, list_index)，index=None 表示该层是 dict。
_POLL_PATH: dict[MineruRoute, tuple[tuple[str, int | None], ...]] = {
    MineruRoute.TASK: (("data", None),),
    MineruRoute.BATCH: (("data", None), ("extract_result", 0)),
}
_POLL_ENDPOINT: dict[MineruRoute, str] = {
    MineruRoute.TASK: "/extract/task",
    MineruRoute.BATCH: "/extract-results/batch",
}


def _resolve(node: object, path: tuple[tuple[str, int | None], ...]) -> dict:
    """按 (key, index) 序列下钻。任一层缺失/类型不符抛 KeyError/TypeError/IndexError。

    与原先 `payload["data"]["state"]` 的失败面一致 —— 这些异常会被
    `classify_external_error` 归成 PARSE。
    """
    for key, idx in path:
        node = node[key]                                  # type: ignore[index]
        if idx is not None:
            node = node[idx]                              # type: ignore[index]
    return node                                           # type: ignore[return-value]


def poll_once(handle: MineruHandle, token: str, *, task_id: str,
              api_base: str | None = None) -> str | None:
    """单次轮询（不 sleep，由调用方控节奏，便于测试）。

    返回：zip_url（done）/ None（waiting-file | running | 其它中间态）
    抛出：failed / 非 2xx / 解析失败
    """
    url = f"{_api_root(api_base)}{_POLL_ENDPOINT[handle.route]}/{handle.job_id}"
    http_status, payload = _curl_json(url, token=token, task_id=task_id, timeout=20)
    _raise_for_status(http_status, payload, task_id=task_id)

    item = _resolve(payload, _POLL_PATH[handle.route])
    state = item.get("state")
    if state == "done":
        return item["full_zip_url"]
    if state == "failed":
        raise StageMinerUError(
            "MinerU 解析任务失败",
            code=ErrorCode.PIPELINE_MINERU_SERVER,
            # 原始 err_msg 只进 details，不进 message —— message 会经
            # progress → TaskError → 响应体到达终端用户。
            context=ErrorContext(
                provider="mineru", stage=PipelineStage.MINERU,
                task_id=task_id, retryable=False,
                details={"job_id": handle.job_id,
                         "err_msg": str(item.get("err_msg") or "")},
            ),
        )
    return None       # waiting-file / running / 未知中间态 → 继续等


def poll_until_done(handle: MineruHandle, token: str, *, task_id: str,
                    api_base: str | None = None) -> str:
    """轮询到终态，返回 zip_url。超时抛 PIPELINE_MINERU_TIMEOUT。

    `_MAX_POLLS` × `_POLL_INTERVAL_SECONDS` = 约 10 分钟，与改造前一致。
    """
    for _ in range(_MAX_POLLS):
        try:
            zip_url = poll_once(handle, token, task_id=task_id, api_base=api_base)
            if zip_url:
                return zip_url
        except StageMinerUError:
            raise
        except PipelineError as exc:
            if not exc.context.retryable:
                raise
            logger.warning("mineru_poll_retry", task_id=task_id,
                           error_code=exc.code.value, exc_info=True)
        time.sleep(_POLL_INTERVAL_SECONDS)

    raise StageMinerUError(
        f"MinerU 轮询超时（{_MAX_POLLS} 次）",
        code=ErrorCode.PIPELINE_MINERU_TIMEOUT,
        context=ErrorContext(
            provider="mineru", stage=PipelineStage.MINERU, task_id=task_id,
            provider_code="poll_timeout", retryable=True,
            details={"job_id": handle.job_id},
        ),
    )


def download_and_extract(zip_url: str, output_dir: str, *, task_id: str) -> str:
    """独占任务目录，临时解压后原子发布 result；残留目录绝不复用。

    失败保留任务目录以拒绝相同标识重试，避免将半成品视为新结果。
    """
    try:
        os.makedirs(output_dir, exist_ok=False)
        staging_dir = tempfile.mkdtemp(prefix=".working-", dir=output_dir)
        zip_path = os.path.join(staging_dir, "result.zip")
        subprocess.run(["curl", "-s", "-o", zip_path, zip_url],
                       check=True, timeout=120)
        subprocess.run(["unzip", "-o", zip_path, "-d", staging_dir],
                       check=True, timeout=30)
        # 只有完整、可解析且属于本次解压目录的真实文件才能原子发布。
        staging = Path(staging_dir).resolve()
        try:
            markdown = staging / "full.md"
            content_lists = list(staging.glob("*_content_list.json"))
            if not content_lists:
                raise ValueError("missing content list")
            for artifact in [markdown, *content_lists]:
                if (
                    artifact.is_symlink() or artifact.is_junction()
                    or not artifact.is_file()
                    or not artifact.resolve().is_relative_to(staging)
                ):
                    raise ValueError("invalid result artifact")
            for content_list in content_lists:
                if not isinstance(json.loads(content_list.read_text(encoding="utf-8")), list):
                    raise ValueError("content list must be a list")
        except (OSError, ValueError) as exc:
            raise StageMinerUError(
                "MinerU 结果产物缺失、类型错误、链接越界或 JSON 无效；未发布结果",
                code=ErrorCode.PIPELINE_MINERU_PARSE,
                context=ErrorContext(provider="mineru", stage=PipelineStage.MINERU,
                                     task_id=task_id, retryable=False),
            ) from exc
        os.remove(zip_path)
        result_dir = os.path.join(output_dir, "result")
        os.rename(staging_dir, result_dir)
    except subprocess.TimeoutExpired as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        raise StageMinerUError(
            "MinerU 结果目录已存在或下载、解压、发布失败；禁止复用历史目录",
            code=ErrorCode.PIPELINE_MINERU_IO,
            context=ErrorContext(provider="mineru", stage=PipelineStage.MINERU,
                                 task_id=task_id, retryable=True),
        ) from exc
    return result_dir


def submit_url_task(
    file_url: str, token: str, task_id: str,
    ingest_options: dict | None = None, api_base: str | None = None,
) -> MineruHandle:
    """URL 模式：`POST /extract/task` 提交一个公网可访问的 URL。"""
    opts = ingest_options or {}
    payload = json.dumps({
        "url": file_url,
        "language": opts.get("language", "ch"),
        "enable_formula": bool(opts.get("enable_formula", True)),
        "enable_table": bool(opts.get("enable_table", True)),
        "model_version": opts.get("model_version", "pipeline"),
    })

    http_status, data = _curl_json(
        _api_root(api_base) + "/extract/task",
        token=token, task_id=task_id, method="POST", body=payload,
    )
    _raise_for_status(http_status, data, task_id=task_id)

    if not isinstance(data, dict) or data.get("success") is False or data.get("code") not in (None, 0):
        raise classify_external_error(
            RuntimeError("mineru submit failed"),
            stage=PipelineStage.MINERU, provider="mineru",
            body_code=(data or {}).get("code") if isinstance(data, dict) else None,
            task_id=task_id,
        )

    try:
        return MineruHandle(route=MineruRoute.TASK, job_id=data["data"]["task_id"])
    except (KeyError, TypeError) as exc:
        raise classify_external_error(
            exc, stage=PipelineStage.MINERU, provider="mineru", task_id=task_id
        ) from exc
