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

from errors import ErrorCode, PipelineError, StageMinerUError
import worker


def _fake_run(stdout: str, exc=None):
    def _run(cmd, **kwargs):
        if exc is not None:
            raise exc
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return _run


def test_submit_http_401_raises_auth(monkeypatch):
    """MinerU 的鉴权失败是 **HTTP 401 + 无 code 字段**的响应体。

    实测响应（2026-09-18，过期 Token）：
        HTTP 401 {"msgCode":"A0202","msg":"user authenticate failed","success":false}
    注意用的是**字符串** msgCode、且没有 `code` —— 所以不可能靠 body 分类，
    必须靠 `curl -w "%{http_code}"` 取回的状态码。

    回归守卫：此前实现用 `curl -s`（丢掉状态码）+ 读 `data["code"]`，
    真实 401 会被误分类成 UNKNOWN；再往前（负数业务码那版）则是 PARSE。
    """
    body = json.dumps({"msgCode": "A0202", "msg": "user authenticate failed",
                       "success": False, "data": None})
    monkeypatch.setattr(subprocess, "run", _fake_run(f"{body}\n401"))
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


def test_submit_http_401_with_html_body_still_auth(monkeypatch):
    """401 带 HTML 错误页（非 JSON）时，状态码不得因解析失败而丢失。"""
    monkeypatch.setattr(subprocess, "run",
                        _fake_run("<html><body>401 Unauthorized</body></html>\n401"))
    with pytest.raises(StageMinerUError) as ei:
        worker._call_mineru_api("http://x/f.pdf", "tok", "task1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_AUTH


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


# ── 本地直传路径（/file-urls/batch + PUT）的失败分类 ─────────────────────────
#
# 回归背景：`put_file` 曾直接 `raise _http_status_error(status)`，而
# `_HttpStatusError` 继承 Exception 而非 PipelineError —— 于是 403 会穿透
# `submit_local_file` 的重试循环与 `_resolve_mineru_dir` 的三级回退链，最终
# 落到 routes/ingest.py 的兜底 except，用户只看到"服务器内部错误"。
# 预签名 URL 过期正是走这条路径的**常见**失败（403），即重试机制本来要处理的
# 那种。以下测试锁住该行为。

from mineru_client import (
    LocalFileUpload, MineruRoute, put_file, submit_local_file,
)


def _ok_apply_body():
    return json.dumps({
        "code": 0, "msg": "ok",
        "data": {"batch_id": "b1", "file_urls": ["https://oss.example/x?Signature=sig"]},
    })


def test_put_403_raises_pipeline_error(monkeypatch):
    """PUT 403 必须抛 PipelineError（可被上层重试/回退捕获），而非裸 _HttpStatusError。"""
    up = LocalFileUpload(batch_id="b1", upload_url="https://oss.example/x", filename="x.pdf")
    monkeypatch.setattr(subprocess, "run", _fake_run("SignatureDoesNotMatch\n403"))
    with pytest.raises(PipelineError) as ei:
        put_file(up, "x.pdf", task_id="t1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_AUTH


def test_put_403_is_not_retryable_and_propagates(monkeypatch):
    """403（签名过期/不匹配）不可重试：重试同一个已过期的签名没有意义。"""
    up = LocalFileUpload(batch_id="b1", upload_url="https://oss.example/x", filename="x.pdf")
    monkeypatch.setattr(subprocess, "run", _fake_run("\n403"))
    with pytest.raises(PipelineError) as ei:
        put_file(up, "x.pdf", task_id="t1")
    assert ei.value.context.retryable is False


def test_submit_local_file_retries_only_retryable_put_failure(monkeypatch):
    """PUT 5xx（可重试）→ 应**重新申请 URL** 再试一次（不能重放旧签名）。

    断言两次 apply 的 URL 不同（第二次是新申请的），证明重试走的是
    "重新申请"而非"重放"。
    """
    calls = {"apply": 0, "urls": []}

    def _run(cmd, **kwargs):
        if "file-urls/batch" in " ".join(cmd):
            calls["apply"] += 1
            url = f"https://oss.example/x?Signature=sig{calls['apply']}"
            calls["urls"].append(url)
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({
                "code": 0, "data": {"batch_id": "b1", "file_urls": [url]},
            }) + "\n200", stderr="")
        # PUT：第一次 500，第二次成功
        if "-X" in cmd and "PUT" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout=("\n500" if calls["apply"] == 1 else "\n200"), stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    handle = submit_local_file("tok", local_path="x.pdf", filename="x.pdf", task_id="t1")
    assert handle.route is MineruRoute.BATCH
    assert calls["apply"] == 2, f"应重新申请 URL 后重试，实际 apply {calls['apply']} 次"
    assert calls["urls"][0] != calls["urls"][1], "重试必须重新申请，不能重放旧签名"


def test_submit_local_file_does_not_retry_auth_failure(monkeypatch):
    """apply 401 不可重试 → 只调一次，立即上抛。"""
    calls = {"apply": 0}

    def _run(cmd, **kwargs):
        if "file-urls/batch" in " ".join(cmd):
            calls["apply"] += 1
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout='{"msgCode":"A0202","msg":"auth failed"}\n401', stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="\n200", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    with pytest.raises(PipelineError) as ei:
        submit_local_file("tok", local_path="x.pdf", filename="x.pdf", task_id="t1")
    assert ei.value.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert calls["apply"] == 1, "鉴权失败不该重试"
