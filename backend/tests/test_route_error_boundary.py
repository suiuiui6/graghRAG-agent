from tests.request_helpers import authenticated_client
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
def client(monkeypatch, sandbox_tmp_path):
    from server import app
    return authenticated_client(app, monkeypatch, sandbox_tmp_path, raise_server_exceptions=False)


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

    monkeypatch.setattr(q, "_build_agent", lambda graph: object())
    monkeypatch.setattr(q, "_invoke_legacy_agent", _boom)

    r = client.post("/api/v1/query", json={"query": "测试问题"})
    assert SENTINEL not in r.text, f"响应体泄露了内部异常文本：{r.text[:300]}"
    assert r.status_code == 503


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
