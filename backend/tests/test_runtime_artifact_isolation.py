"""Tests must never persist indexes into the user's runtime directory."""
import hashlib
import importlib
import json
from pathlib import Path

import index_registry


def test_runtime_artifact_defaults_remain_isolated_after_module_reload(tmp_path):
    original_path = Path(__file__).parents[1] / 'output/runtime/table_artifact.json'
    before = hashlib.sha256(original_path.read_bytes()).hexdigest()
    registry = importlib.reload(index_registry)
    assert registry.BM25_ARTIFACT_PATH.is_relative_to(tmp_path)
    assert registry.TABLE_ARTIFACT_PATH.is_relative_to(tmp_path)
    table = registry.RestoredTableIndex([{'sheet_name': 'test fixture', 'value': 42}])
    registry.snapshot_table_index(index=table)
    assert json.loads(registry.TABLE_ARTIFACT_PATH.read_text(encoding='utf-8'))['rows'] == table.rows
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() == before


def test_snapshot_failure_preserves_previously_valid_artifact(tmp_path, monkeypatch):
    path = tmp_path / 'table-snapshot.json'
    previous = b'{"rows":[{"value":42}]}'
    path.write_bytes(previous)
    monkeypatch.setattr(index_registry, 'TABLE_ARTIFACT_PATH', path)
    class UnavailableTable:
        def query(self, *args, **kwargs):
            raise OSError('transient table unavailable')
    assert index_registry.snapshot_table_index(index=UnavailableTable()) is None
    assert path.read_bytes() == previous
