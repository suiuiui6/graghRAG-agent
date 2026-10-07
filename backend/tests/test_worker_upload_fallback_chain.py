"""本地文件上传的三级降级链：MinerU 直传 → OSS → 本地缓存。

不打网络：只在进程边界 monkeypatch `worker` 上的三个接缝。
被测的是**编排顺序与判定**（谁是默认、失败后回退到哪、什么情况不回退）。

注意：不驱动整个 `_run_real_pipeline_inner` —— 那会把 bridge/KG 阶段也拉进来，
失败原因与上传无关、测试变得脆弱且难定位。这里只驱动 Stage 0 的决策。
"""
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (
    ErrorCode, ErrorContext, PipelineStage, StageMinerUError,
)
import worker


def _stage_error(code: ErrorCode, retryable: bool = False) -> StageMinerUError:
    return StageMinerUError(
        "boom", code=code,
        context=ErrorContext(provider="mineru", stage=PipelineStage.MINERU,
                             retryable=retryable),
    )


def _run_stage0(monkeypatch, *, direct, oss, cache=None, allow_cache=False):
    """直接驱动 `_resolve_mineru_dir`（Stage 0），返回 (结果, 调用记录)。

    结果 == 目录字符串 或 一个 StageMinerUError。
    只打桩三个外部接缝，其余逻辑真实执行。
    """
    rec = {"direct": 0, "oss": 0}

    def _direct(filepath, token, task_id, ingest_options=None):
        rec["direct"] += 1
        return direct()

    def _oss_upload(filepath):
        # 只有前一级失败时才应被调用 —— 用于断言"默认路径不回退"
        rec["oss"] += 1
        return oss()

    monkeypatch.setattr(worker, "_call_mineru_local_file", _direct)
    monkeypatch.setattr(worker, "_upload_to_public", _oss_upload)
    monkeypatch.setattr(worker, "_call_mineru_api", lambda url, t, tid, o=None: "DIR_FROM_OSS")
    monkeypatch.setattr(worker, "_find_cached_mineru_output", lambda root=None: cache)

    opts = {"allow_cached_mineru_output": allow_cache}
    try:
        return worker._resolve_mineru_dir(
            "t1", "uploads/probe.pdf", opts, lambda *a, **k: None), rec
    except StageMinerUError as exc:
        return exc, rec


def test_mineru_direct_is_default_and_oss_not_called(monkeypatch):
    """默认走 MinerU 直传；**OSS 不得被调用**。

    这是防"默认路径悄悄退回 OSS"的承重断言 —— 没有它，将来有人把顺序改回去
    也不会有任何测试失败。
    """
    result, rec = _run_stage0(monkeypatch,
                              direct=lambda: "DIRECT_OK",
                              oss=lambda: "https://oss/x.pdf")
    assert result == "DIRECT_OK", result
    assert rec["direct"] == 1
    assert rec["oss"] == 0, "直传成功时不得碰 OSS"


def test_falls_back_to_oss_when_direct_fails(monkeypatch):
    def _fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_SERVER, retryable=True)

    result, rec = _run_stage0(monkeypatch, direct=_fail,
                              oss=lambda: "https://oss/x.pdf")
    assert result == "DIR_FROM_OSS", result
    assert rec["direct"] == 1
    assert rec["oss"] == 1, "直传失败后应尝试 OSS"


def test_cache_is_NOT_used_by_default(monkeypatch):
    """**承重断言**：缓存兜底默认关闭。

    若默认开启，MinerU 一抖动就会静默把 output/mineru/ 下**别的文档**的产物
    当成这次的结果入库（缓存按目录名字典序挑，与待入库文件无关）。
    这条测试防止有人"顺手"把默认改回开启。
    """
    def _fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_SERVER, retryable=True)

    result, rec = _run_stage0(monkeypatch, direct=_fail, oss=lambda: None,
                              cache="/cache/hit", allow_cache=False)
    assert isinstance(result, StageMinerUError), "默认不该用缓存，应判失败"
    assert result.code is ErrorCode.PIPELINE_MINERU_IO
    assert rec["direct"] == 1 and rec["oss"] == 1


def test_cache_used_when_explicitly_enabled(monkeypatch):
    """显式 opt-in 时才走缓存兜底。"""
    def _fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_SERVER, retryable=True)

    result, rec = _run_stage0(monkeypatch, direct=_fail, oss=lambda: None,
                              cache="/cache/hit", allow_cache=True)
    assert result == "/cache/hit", result
    assert rec["direct"] == 1 and rec["oss"] == 1


def test_all_three_fail_raises_io_with_attempts(monkeypatch):
    """三级全败 → 判任务失败，且错误里能看出每级都试过、根因归谁。"""
    def _fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_TIMEOUT, retryable=True)

    result, rec = _run_stage0(monkeypatch, direct=_fail, oss=lambda: None, cache=None)
    assert isinstance(result, StageMinerUError)
    assert result.code is ErrorCode.PIPELINE_MINERU_IO
    # 根因归 mineru（主路径），不再是 oss —— 改造后首个失败者是直传
    assert result.context.provider == "mineru"
    assert "attempts" in result.context.details
    assert len(result.context.details["attempts"]) == 2   # 直传 + OSS 各记一条


def test_auth_failure_does_not_fall_through_to_oss(monkeypatch):
    """鉴权失败**立即上抛**，不浪费 OSS 回退预算。

    直传与 URL 模式共用同一个 Token 与同一套参数 —— 回退只会用坏凭据再失败一次。
    这条断言防止把 AUTH 当作可降级，从而把凭据问题掩盖成"上传偶发失败"。
    """
    def _auth_fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_AUTH, retryable=False)

    result, rec = _run_stage0(monkeypatch, direct=_auth_fail,
                              oss=lambda: "https://oss/x.pdf")
    assert isinstance(result, StageMinerUError)
    assert result.code is ErrorCode.PIPELINE_MINERU_AUTH
    assert rec["oss"] == 0, "鉴权失败不该回退到 OSS"


def test_parse_failure_does_not_fall_through_to_oss(monkeypatch):
    """参数/解析类失败同样不回退（换个通道不会修好参数错误）。"""
    def _parse_fail():
        raise _stage_error(ErrorCode.PIPELINE_MINERU_PARSE, retryable=False)

    result, rec = _run_stage0(monkeypatch, direct=_parse_fail,
                              oss=lambda: "https://oss/x.pdf")
    assert isinstance(result, StageMinerUError)
    assert result.code is ErrorCode.PIPELINE_MINERU_PARSE
    assert rec["oss"] == 0


class TestCacheScan:
    """`_find_cached_mineru_output` 的判定条件（真实的目录夹具，非 mock）。"""

    def test_accepts_dir_with_full_md_and_content_list(self, tmp_path):
        d = tmp_path / "doc1"
        d.mkdir()
        (d / "full.md").write_text("# x", encoding="utf-8")
        (d / "abc_content_list.json").write_text("{}", encoding="utf-8")
        assert worker._find_cached_mineru_output(str(tmp_path)) == str(d)

    def test_rejects_dir_missing_content_list(self, tmp_path):
        d = tmp_path / "doc1"
        d.mkdir()
        (d / "full.md").write_text("# x", encoding="utf-8")
        assert worker._find_cached_mineru_output(str(tmp_path)) is None

    def test_rejects_v2_only_content_list(self, tmp_path):
        """只有 `_v2` 变体不算命中 —— 与改造前的过滤条件一致。"""
        d = tmp_path / "doc1"
        d.mkdir()
        (d / "full.md").write_text("# x", encoding="utf-8")
        (d / "abc_content_list_v2.json").write_text("{}", encoding="utf-8")
        assert worker._find_cached_mineru_output(str(tmp_path)) is None

    def test_picks_lexicographically_last(self, tmp_path):
        """取目录名字典序**倒序**第一个（既有行为，本次不改）。"""
        for name in ("aaa", "zzz"):
            d = tmp_path / name
            d.mkdir()
            (d / "full.md").write_text("# x", encoding="utf-8")
            (d / "c_content_list.json").write_text("{}", encoding="utf-8")
        assert worker._find_cached_mineru_output(str(tmp_path)) == str(tmp_path / "zzz")

    def test_missing_root_returns_none(self, tmp_path):
        assert worker._find_cached_mineru_output(str(tmp_path / "nope")) is None
