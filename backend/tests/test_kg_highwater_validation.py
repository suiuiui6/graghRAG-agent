"""Invalid version metadata must fail before retirement or new-version writes."""
import json
from pathlib import Path

import pytest

from kg_store import KgVersionManager
from services import lifecycle


@pytest.mark.parametrize('highwater', [True, False, 99.5, -1, 0, None, '99'])
def test_invalid_highwater_cannot_create_or_retire_any_version(tmp_path, monkeypatch, highwater):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'kg'
    manager = KgVersionManager('strict', root)
    manager.doc_dir.mkdir(parents=True)
    for version in range(12):
        path = manager.doc_dir / f'v{version}'
        path.mkdir()
        (path / 'nodes.json').write_text('[]')
        (path / 'edges.json').write_text('[]')
    meta = {'active_version': 0, 'next_version': highwater,
            'versions': [{'version': v} for v in range(12)]}
    manager.versions_file.write_text(json.dumps(meta), encoding='utf-8')
    original = manager.versions_file.read_bytes()
    monkeypatch.setattr(lifecycle, 'KG_DIR', root)
    with pytest.raises(ValueError):
        manager.create_version([], [])
    assert lifecycle.DataLifecycleManager()._clean_kg_versions() == 0
    assert manager.versions_file.read_bytes() == original
    assert {p.name for p in manager.doc_dir.iterdir() if p.is_dir()} == {f'v{v}' for v in range(12)}
    assert not list(manager.doc_dir.glob('.retired-*'))
