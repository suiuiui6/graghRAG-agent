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

from errors import (
    ErrorCode, StageMinerUError,
    UpstreamUnavailableError, register_exception_handlers,
)

SENTINEL = "INTERNAL-SECRET-SENTINEL-abcdef123456"


class EchoPayload(BaseModel):
    """探针请求模型 —— 计划原稿用 `payload: dict` 会使校验永不触发（FastAPI
    把整个 body 绑给 dict，`test_validation_error_*` 两个用例因而空跑通过）。
    必须有 Pydantic 模型参数才会产生 RequestValidationError。"""
    password: str
    n: int


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

    @app.post("/echo")
    async def echo(payload: EchoPayload):
        return payload.model_dump()

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
