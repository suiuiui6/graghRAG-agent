"""离线回归：任务完整标识、独占目录及无身份校验缓存禁用。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mineru_client
import worker
from errors import ErrorCode, StageMinerUError


@pytest.mark.parametrize("entry", ["url", "local"])
def test_full_task_ids_with_same_prefix_have_distinct_outputs(monkeypatch, tmp_path, entry):
    monkeypatch.setattr(worker, "__file__", str(tmp_path / "worker.py"))
    monkeypatch.setattr(worker, "submit_url_task", lambda *a, **k: "handle")
    monkeypatch.setattr(worker, "submit_local_file", lambda *a, **k: "handle")
    monkeypatch.setattr(worker, "poll_until_done", lambda *a, **k: "zip")
    monkeypatch.setattr(worker, "download_and_extract", lambda url, out, **k: out)
    ids = ["ingest_a1111111111111111111111111111111", "ingest_a2222222222222222222222222222222"]
    call = worker._call_mineru_api if entry == "url" else worker._call_mineru_local_file
    outputs = [Path(call("probe.pdf", "unused", tid)) for tid in ids]
    assert outputs[0] != outputs[1]
    assert [out.name for out in outputs] == ids


@pytest.mark.parametrize("task_id", ["../outside", "bad/id", "bad\\id", "", "C:escape", "CON"])
@pytest.mark.parametrize("entry", ["url", "local"])
def test_unsafe_task_id_rejected_before_supplier_call(monkeypatch, task_id, entry):
    calls = []
    monkeypatch.setattr(worker, "submit_url_task", lambda *a, **k: calls.append("url"))
    monkeypatch.setattr(worker, "submit_local_file", lambda *a, **k: calls.append("local"))
    monkeypatch.setattr(worker, "poll_until_done", lambda *a, **k: "zip")
    monkeypatch.setattr(worker, "download_and_extract", lambda *a, **k: "unused")
    call = worker._call_mineru_api if entry == "url" else worker._call_mineru_local_file
    with pytest.raises(StageMinerUError) as exc:
        call("probe.pdf", "unused", task_id)
    assert exc.value.code is ErrorCode.PIPELINE_MINERU_PARSE
    assert calls == []


def test_existing_output_is_never_reused_or_overwritten(monkeypatch, tmp_path):
    output = tmp_path / "ingest_same"
    output.mkdir()
    marker = output / "full.md"
    marker.write_text("历史文档", encoding="utf-8")
    calls = []
    monkeypatch.setattr(mineru_client.subprocess, "run", lambda *a, **k: calls.append(a))
    with pytest.raises(StageMinerUError) as exc:
        mineru_client.download_and_extract("unused", str(output), task_id="ingest_same")
    assert exc.value.code is ErrorCode.PIPELINE_MINERU_IO
    assert calls == []
    assert marker.read_text(encoding="utf-8") == "历史文档"


def test_same_output_concurrent_attempt_has_only_one_writer(monkeypatch, tmp_path):
    output = tmp_path / "ingest_same"
    entered = threading.Event()
    release = threading.Event()

    def run(cmd, **kwargs):
        if cmd[0] == "curl":
            entered.set()
            assert release.wait(5)
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"fixture")
        else:
            Path(cmd[-1], "full.md").write_text("本次文档", encoding="utf-8")
            Path(cmd[-1], "paper_content_list.json").write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mineru_client.subprocess, "run", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(mineru_client.download_and_extract, "unused", str(output), task_id="ingest_same")
        assert entered.wait(5)
        try:
            with pytest.raises(StageMinerUError):
                mineru_client.download_and_extract("unused", str(output), task_id="ingest_same")
        finally:
            release.set()
        assert first.result() == str(output / "result")
    assert (output / "result" / "full.md").read_text(encoding="utf-8") == "本次文档"


@pytest.mark.parametrize("entry", ["url", "local"])
def test_distinct_concurrent_tasks_publish_only_their_own_contents(monkeypatch, tmp_path, entry):
    monkeypatch.setattr(worker, "__file__", str(tmp_path / "worker.py"))
    monkeypatch.setattr(worker, "submit_url_task", lambda url, token, tid, opts: tid)
    monkeypatch.setattr(worker, "submit_local_file", lambda token, **kw: kw["task_id"])
    monkeypatch.setattr(worker, "poll_until_done", lambda handle, *a, **k: handle)
    barrier = threading.Barrier(2)

    def run(cmd, **kwargs):
        if cmd[0] == "curl":
            barrier.wait(timeout=5)
            Path(cmd[cmd.index("-o") + 1]).write_text(cmd[-1], encoding="utf-8")
        else:
            staging = Path(cmd[-1])
            assert not (staging.parent / "result").exists()
            (staging / "full.md").write_text((staging / "result.zip").read_text(encoding="utf-8"), encoding="utf-8")
            (staging / "paper_content_list.json").write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mineru_client.subprocess, "run", run)
    ids = ["ingest_a1111", "ingest_a2222"]
    call = worker._call_mineru_api if entry == "url" else worker._call_mineru_local_file
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call, "probe.pdf", "unused", tid) for tid in ids]
        outputs = [Path(f.result()) for f in futures]
    assert outputs[0] != outputs[1]
    for task_id, output in zip(ids, outputs):
        assert output.parent.name == task_id
        assert (output / "full.md").read_text(encoding="utf-8") == task_id
        assert list(output.parent.glob(".working-*")) == []


def test_failed_download_never_publishes_and_cannot_reuse_residue(monkeypatch, tmp_path):
    output = tmp_path / "ingest_failed"

    def fail(cmd, **kwargs):
        Path(cmd[cmd.index("-o") + 1]).write_text("半成品", encoding="utf-8")
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(mineru_client.subprocess, "run", fail)
    with pytest.raises(StageMinerUError) as exc:
        mineru_client.download_and_extract("unused", str(output), task_id="ingest_failed")
    assert exc.value.code is ErrorCode.PIPELINE_MINERU_TIMEOUT
    assert not (output / "result").exists()
    assert list(output.glob(".working-*/result.zip"))
    with pytest.raises(StageMinerUError) as exc:
        mineru_client.download_and_extract("unused", str(output), task_id="ingest_failed")
    assert exc.value.code is ErrorCode.PIPELINE_MINERU_IO
    assert not (output / "result").exists()


@pytest.mark.parametrize("allow_cache", [False, True])
def test_old_complete_cache_never_becomes_new_upload_result(monkeypatch, tmp_path, allow_cache):
    old = tmp_path / "output" / "mineru" / "zzz_old"
    old.mkdir(parents=True)
    (old / "full.md").write_text("其他文档", encoding="utf-8")
    (old / "old_content_list.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(worker, "__file__", str(tmp_path / "worker.py"))

    def fail(*a, **k):
        raise StageMinerUError("离线", code=ErrorCode.PIPELINE_MINERU_IO)

    monkeypatch.setattr(worker, "_call_mineru_local_file", fail)
    monkeypatch.setattr(worker, "_upload_to_public", lambda *a: None)
    with pytest.raises(StageMinerUError) as exc:
        worker._resolve_mineru_dir("ingest_new", "probe.pdf", {"allow_cached_mineru_output": allow_cache}, lambda *a, **k: None)
    assert exc.value.code is ErrorCode.PIPELINE_MINERU_IO
    assert "缓存" in exc.value.context.details["hint"]
    assert (old / "full.md").read_text(encoding="utf-8") == "其他文档"


def _use_local_result_zip(monkeypatch, root, files, linked_name=None):
    archive = root / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name, content in files.items():
            stream.writestr(name, content)
    real_run = subprocess.run

    def run(cmd, **kwargs):
        if cmd[0] == "curl":
            shutil.copyfile(archive, cmd[cmd.index("-o") + 1])
            return subprocess.CompletedProcess(cmd, 0)
        # Windows 沙箱不允许 Git/MSYS unzip 创建命名对象；仍以独立进程真实解压 ZIP。
        result = real_run([sys.executable, "-m", "zipfile", "-e", cmd[2], cmd[-1]], **kwargs)
        if linked_name:
            target = root / "outside-artifact"
            target.write_text(files[linked_name], encoding="utf-8")
            extracted = Path(cmd[-1]) / linked_name
            extracted.unlink()
            extracted.symlink_to(target)
        return result

    monkeypatch.setattr(mineru_client.subprocess, "run", run)


@pytest.mark.parametrize("bad_artifact", ["missing_md", "missing_list", "malformed", "non_list", "linked_md", "linked_list"])
def test_invalid_extracted_artifacts_never_publish(monkeypatch, sandbox_tmp_path, bad_artifact):
    files = {"full.md": "表格内容", "paper_content_list.json": "[]"}
    linked_name = None
    if bad_artifact == "missing_md":
        del files["full.md"]
    elif bad_artifact == "missing_list":
        del files["paper_content_list.json"]
    elif bad_artifact == "malformed":
        files["paper_content_list.json"] = "{invalid"
    elif bad_artifact == "non_list":
        files["paper_content_list.json"] = "{}"
    elif bad_artifact.startswith("linked_"):
        linked_name = "full.md" if bad_artifact == "linked_md" else "paper_content_list.json"
    _use_local_result_zip(monkeypatch, sandbox_tmp_path, files, linked_name)
    output = sandbox_tmp_path / "task"

    with pytest.raises(StageMinerUError) as exc:
        mineru_client.download_and_extract("local-fixture", str(output), task_id="task")

    assert exc.value.code is ErrorCode.PIPELINE_MINERU_PARSE
    assert not (output / "result").exists()
    assert list(output.glob(".working-*"))


def test_valid_real_zip_is_published_after_validation(monkeypatch, sandbox_tmp_path):
    files = {"full.md": "本次文档", "paper_content_list.json": '[{"type":"text","text":"本次文档"}]'}
    _use_local_result_zip(monkeypatch, sandbox_tmp_path, files)
    output = sandbox_tmp_path / "task"

    assert mineru_client.download_and_extract("local-fixture", str(output), task_id="task") == str(output / "result")
    for name, text in files.items():
        assert (output / "result" / name).read_text(encoding="utf-8") == text
    assert list(output.glob(".working-*")) == []
