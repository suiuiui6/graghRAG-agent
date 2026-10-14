"""恢复扫描只采用已发布产物，兼容旧布局并拒绝链接越界。"""
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def _write_source(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "full.md").write_text("表格内容", encoding="utf-8")
    (path / "paper_content_list.json").write_text("[]", encoding="utf-8")
    return path


def test_new_published_result_and_legacy_sources_remain_ordered(monkeypatch, sandbox_tmp_path):
    root = sandbox_tmp_path / "mineru"
    legacy = _write_source(root / "legacy")
    task = root / "ingest_complete_task_id"
    published = _write_source(task / "result")
    os.utime(legacy, (100, 100))
    os.utime(task, (200, 200))
    monkeypatch.setattr(server, "MINERU_OUTPUT_DIR", root)

    assert server._iter_mineru_runtime_sources() == [
        (published, "ingest_complete_task_id.pdf"), (legacy, "legacy.pdf"),
    ]
    assert server._find_latest_mineru_runtime_source() == (published, "ingest_complete_task_id.pdf")


def test_unpublished_working_directories_are_never_sources(monkeypatch, sandbox_tmp_path):
    root = sandbox_tmp_path / "mineru"
    _write_source(root / "task" / ".working-secret")
    _write_source(root / ".working-top-level")
    _write_source(root / "partial" / "result")
    (root / "partial" / "result" / "full.md").unlink()
    monkeypatch.setattr(server, "MINERU_OUTPUT_DIR", root)

    assert server._iter_mineru_runtime_sources() == []


@pytest.mark.parametrize("linked_part", ["task", "result", "markdown", "content_list", "root"])
def test_sources_reject_symlinks_outside_output(monkeypatch, sandbox_tmp_path, linked_part):
    root = sandbox_tmp_path / "mineru"
    outside = _write_source(sandbox_tmp_path / "outside")
    root.mkdir()
    if linked_part == "root":
        root.rmdir()
        target = sandbox_tmp_path / "outside_root"
        _write_source(target / "legacy")
        root.symlink_to(target, target_is_directory=True)
    elif linked_part == "task":
        (root / "task").symlink_to(outside, target_is_directory=True)
    elif linked_part == "result":
        (root / "task").mkdir()
        (root / "task" / "result").symlink_to(outside, target_is_directory=True)
    else:
        legacy = _write_source(root / "legacy")
        name = "full.md" if linked_part == "markdown" else "paper_content_list.json"
        (legacy / name).unlink()
        (legacy / name).symlink_to(outside / name)
    monkeypatch.setattr(server, "MINERU_OUTPUT_DIR", root)

    assert server._iter_mineru_runtime_sources() == []


def test_artifact_directories_do_not_count_as_files(monkeypatch, sandbox_tmp_path):
    root = sandbox_tmp_path / "mineru"
    legacy = root / "legacy"
    (legacy / "full.md").mkdir(parents=True)
    (legacy / "paper_content_list.json").mkdir()
    monkeypatch.setattr(server, "MINERU_OUTPUT_DIR", root)

    assert server._iter_mineru_runtime_sources() == []


def test_missing_output_has_no_sources(monkeypatch, sandbox_tmp_path):
    monkeypatch.setattr(server, "MINERU_OUTPUT_DIR", sandbox_tmp_path / "missing")
    assert server._iter_mineru_runtime_sources() == []
