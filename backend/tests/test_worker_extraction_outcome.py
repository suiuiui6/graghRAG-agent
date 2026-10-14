"""抽取三态可分：全失败 / 部分失败 / 零实体 —— 改造前全部退化为 (0,0)。"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import ErrorCode, StageExtractionError
import worker


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
