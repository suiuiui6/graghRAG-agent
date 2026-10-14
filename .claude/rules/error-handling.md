---
paths:
  - "backend/**/*.py"
---
# 规则：Python 错误处理与日志

> 来源：developer-kit `python/rules/error-handling.md`，已按本项目现状裁剪。
> 对应 backlog F003/F004/B38/B39。
>
> **状态：F003/F004 已于 2026-09-18 落地**（计划 `docs/superpowers/plans/2026-09-18-logging-exception-governance.md`）。
> 改造前后指标（均为实测，非估算）：
>
> | 指标 | 改造前 | 改造后 |
> |---|---|---|
> | 非 CLI 库代码 `print()` | 28 | **0**（5 个真 CLI 入口的 109 处保留，见 `pyproject.toml` 的 per-file-ignores） |
> | 裸 `except:` | 1 | **0** |
> | 静默吞异常（`pass`/`continue`/`return None`） | 116 | **0**（逐处带 `# noqa: S110, BLE001  # 理由`） |
> | `except Exception` 总数 | 229 | 227（**未清零是设计使然**：宽捕本身合理，要求是每处带理由，见下） |
> | 生产模块使用 stdlib `logging` | 5 | **0**（全部走 `logging_config.get_logger`，否则绕过脱敏链） |
> | `exc_info=True` 是否保留堆栈 | 否（只输出 `{"exc_info": true}`） | **是**（processor 链补了 `format_exc_info`） |
>
> **强制手段**：`backend/pyproject.toml` 的 `[tool.ruff]`（E722 / BLE001 / S110 / T20 / RUF100）
> + `backend/tests/test_error_handling_policy.py` 的策略守卫 + CI 的 `bandit-sast` job。
> 门禁已开，新增违规会被 CI 拦下。

## 异常处理

- **禁止裸 `except:`**，禁止静默吞异常（`except: pass`）
- 禁止 `return None` 掩盖真实失败——上游会把它当成成功继续跑
- 外部调用（MinerU / LangExtract / OSS / LLM）按错误分类处理：`401`（凭证）、`429`（限流）、`5xx`（服务端）、`timeout`，分别退避重试或明确失败
- 顶层边界用 `raise NewError("...") from original_error` 保留原始 traceback
- 建立分层错误码：五阶段（解析/分段/抽取/溯源/建图）+ 前端可读提示

```python
# ✅ 好
class PipelineError(Exception):
    """五阶段流水线统一错误基类。"""

class StageMinerUError(PipelineError):
    """解析阶段失败，携带 provider 信息。"""

def _call_mineru_api(...):
    try:
        resp = client.post(...)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise StageMinerUError("MinerU 凭证无效") from e
        if e.response.status_code == 429:
            raise StageMinerUError("MinerU 触发限流，稍后重试") from e
        raise StageMinerUError(f"MinerU 服务异常 {e.response.status_code}") from e

# ❌ 坏（本项目现状）
try:
    result = call_mineru()
except Exception:
    return None   # 上游会误以为成功，或用旧缓存顶替
```

## 日志

- **业务代码禁止 `print()`**（仅 CLI 入口如 `agentic_rag_mvp.py` 可保留）
- 统一使用 `structlog`（`logging_config.py` 已存在），JSON 格式
- 每个请求/任务日志携带 `request_id` / `task_id` / `trace_id` 关联字段
- **日志输出禁止出现 API Key / Token**；用 `structlog` 处理器脱敏

```python
# ✅ 好
import structlog
logger = structlog.get_logger(__name__)
logger.info("indexing_started", task_id=task_id, stage="mineru", file_size=size)

# ❌ 坏
print(f"[mineru] task {task_id} done, token={api_key}")  # 泄露凭据
```

## 校验

- 输入校验放在边界（Pydantic），不在业务逻辑深处手工校验
- 文件名/路径用 `Path.resolve()` + `is_relative_to()` 防路径穿越（见 python-security-expert）
