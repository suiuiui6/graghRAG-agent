"""Exercise the maintenance CLI against disposable logs only."""
import sys

import pytest

from scripts import purge_log_secrets as scrubber


@pytest.mark.parametrize('apply', [False, True])
def test_scrubber_preview_apply_and_idempotence(tmp_path, monkeypatch, capsys, apply):
    logs = tmp_path / 'logs'
    logs.mkdir()
    nested = logs / 'nested'
    nested.mkdir()
    original = 'Bearer synthetic_fixture_token sk-synthetic_fixture_token\n'
    changed = nested / 'service.log.1'
    changed.write_text(original, encoding='utf-8')
    clean = logs / 'clean.log'
    clean.write_text('ordinary diagnostic', encoding='utf-8')
    ignored = logs / 'unrelated.txt'
    ignored.write_text(original, encoding='utf-8')
    (logs / 'directory.log').mkdir()
    monkeypatch.setattr(scrubber, 'LOG_DIR', logs)
    monkeypatch.setattr(sys, 'argv', ['purge-log-secrets', *(['--apply'] if apply else [])])
    assert scrubber.main() == 0
    output = capsys.readouterr().out
    assert '2 处' in output
    assert 'synthetic_fixture_token' not in output
    assert changed.read_text(encoding='utf-8') == (
        'Bearer [REDACTED] [REDACTED]\n' if apply else original)
    assert clean.read_text(encoding='utf-8') == 'ordinary diagnostic'
    assert ignored.read_text(encoding='utf-8') == original
    assert not list(logs.rglob('*.tmp'))
    if apply:
        assert scrubber.main() == 0
        assert '清理 0 处' in capsys.readouterr().out
    else:
        assert '加 --apply' in output


def test_scrubber_absent_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scrubber, 'LOG_DIR', tmp_path / 'absent')
    monkeypatch.setattr(sys, 'argv', ['purge-log-secrets'])
    assert scrubber.main() == 0
    assert '无需清理' in capsys.readouterr().out
    assert not (tmp_path / 'absent').exists()


def test_scrubber_all_formats_and_clean_text():
    text = ('{"file_access_token": "0123456789abcdef"}\n'
            'Bearer synthetic_fixture_token\nsk-synthetic_fixture_token\n'
            'LTAIabcdefghijkl\n')
    cleaned, count = scrubber.scrub_text(text)
    assert count == 4
    assert cleaned.count('[REDACTED]') == 4
    assert scrubber.scrub_text(cleaned) == (cleaned, 0)
    assert scrubber.scrub_text('ordinary error') == ('ordinary error', 0)
