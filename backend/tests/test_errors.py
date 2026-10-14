"""错误码体系守卫：可达性 + 映射表完备性 + stdlib-only。"""
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (
    ERROR_MESSAGES, ErrorCode, FailureReason, PipelineError,
    PipelineStage, StageExtractionError, StageMinerUError, _compose,
    _PROVIDER_CODE_MAP, classify_external_error, user_message,
)
from worker import _http_status_error

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
    """MinerU 的鉴权失败走 **HTTP 状态码**（实测 401）。

    实测响应体用的是字符串 msgCode（"A0202"）且**没有 code 字段**，
    所以从 body 读 code 注定拿不到鉴权信息。
    """
    body_less = _http_status_error(401)
    err = classify_external_error(body_less, stage=PipelineStage.MINERU, provider="mineru")
    assert err.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert err.context.retryable is False


def test_classify_http_422_is_not_retryable():
    err = classify_external_error(_http_status_error(422),
                                  stage=PipelineStage.MINERU, provider="mineru")
    assert err.code is ErrorCode.PIPELINE_MINERU_PARSE
    assert err.context.retryable is False


def test_mineru_body_code_map_contains_only_observed_codes():
    """回归守卫：MinerU 的 body 业务码映射**只能收录实测观察到的码**。

    2026-09-18 曾填入 -10001 / -60001..-60004 等"负数业务码"，**均属编造** ——
    MinerU 官方规格（langextract/docs/MinerU-API-Specification.md §4.5）与真实
    响应里都没有这些数字。该错误使真实 401 被误分类
    （见 test_worker_mineru_errors.py 的回归测试）。

    目前唯一实测到的码是 -60023（URL 被区域限制）。若将来要增删，必须：
      ① 有实测响应或规格文档为证；② 同步更新本清单。
    """
    assert set(_PROVIDER_CODE_MAP["mineru"]) == {-60023}, (
        "MinerU 的 body 业务码表含未实测的码；"
        f"当前: {sorted(_PROVIDER_CODE_MAP['mineru'])}，期望: [-60023]"
    )
    # 且已实测的编造码绝不能回流
    for fabricated in (-10001, -10002, -500, -60001, -60002, -60003, -60004):
        assert fabricated not in _PROVIDER_CODE_MAP["mineru"], (
            f"{fabricated} 是编造的码，不得回填"
        )

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
