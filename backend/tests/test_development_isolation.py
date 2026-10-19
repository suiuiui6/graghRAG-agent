from pathlib import Path
import pytest
from research.development_isolation import prepare, checked_path, grounding_evidence


def test_prepare_copies_only_owned_source_and_no_secrets_or_outputs(tmp_path):
    repo = tmp_path / 'repo'; (repo / 'backend/config').mkdir(parents=True)
    (repo / 'backend/a.py').write_text('value=1')
    (repo / 'backend/.env').write_text('secret')
    (repo / 'backend/output').mkdir(); (repo / 'backend/output/a.py').write_text('private')
    (repo / 'backend/config/extraction_examples.yaml').write_text('examples: []')
    (repo / 'langextract/langextract').mkdir(parents=True)
    (repo / 'langextract/langextract/__init__.py').write_text('')
    run = tmp_path / 'run'; manifest = prepare(repo, run)
    assert (run / 'backend/a.py').read_text() == 'value=1'
    assert not (run / 'backend/.env').exists()
    assert not (run / 'backend/output/a.py').exists()
    assert manifest['files']
    with pytest.raises(FileExistsError): prepare(repo, run)


def test_checked_path_rejects_escape(tmp_path):
    with pytest.raises(ValueError): checked_path(tmp_path, tmp_path / '../escape')


def test_strict_interval_evidence_distinguishes_native_grounded_fuzzy():
    from types import SimpleNamespace
    ext = SimpleNamespace(extraction_text='DIFFERENT', char_interval=(1, 4), grounding_status='grounded')
    result = grounding_evidence('abcde', ext)
    assert result['native_grounding_status'] == 'grounded'
    assert result['source_interval_valid'] is True
    assert result['exact_text_match'] is False
    assert result['source_slice'] == 'bcd'


def test_simulated_preflight_uses_only_local_transport_and_labels_output(tmp_path, monkeypatch):
    import research.development_isolation as isolation
    from types import SimpleNamespace
    monkeypatch.setattr(isolation, '_source_units', lambda p: [({'source_id': 'S'}, 'source', Path('source.html'), [])])
    monkeypatch.setattr(isolation, '_bridge_source', lambda *a: ([], None, [SimpleNamespace()], {}))
    monkeypatch.setattr(isolation, 'module_identity', lambda *a: {'fixture_only': True})
    monkeypatch.setattr(isolation, 'verify_snapshot', lambda *a: {})
    # This small seam substitutes only the native extraction invocation. Wire
    # capture/redirection is real and tested independently with the actual SDK.
    import sys
    def extract(documents):
        import langextract.factory as factory
        import os
        model = factory.create_model(factory.ModelConfig(model_id='deepseek-flash', provider='openai', provider_kwargs={'api_key': os.environ['LANGEXTRACT_API_KEY'], 'base_url': 'https://api.deepseek.com'}))
        result = model._process_single_prompt('source', model._extra_kwargs)
        assert result.output
        return []
    monkeypatch.setitem(sys.modules, 'worker', SimpleNamespace(_run_langextract=extract))
    result = isolation.preflight_sources(tmp_path, 'manifest', 'xml')
    assert result['mode'] == 'SIMULATED_NO_PROVIDER_USAGE'
    assert result['planned_requests'] == 1
    assert result['requests'][0]['phase'] == 'index'
    assert not (tmp_path / 'ledger.json').exists()


def test_module_identity_rejects_import_outside_snapshot(tmp_path, monkeypatch):
    import research.development_isolation as isolation
    import sys
    from types import SimpleNamespace
    (tmp_path / 'snapshot.json').write_text('{"files": {}}')
    monkeypatch.setitem(sys.modules, 'fake_native_module', SimpleNamespace(__file__=str(tmp_path / '../outside.py')))
    with pytest.raises(ValueError): isolation.module_identity(tmp_path, ('fake_native_module',))
