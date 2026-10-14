"""Guard tests use tiny files and fresh short-lived interpreters only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(os.environ.get('GUARD_TEST_MODULE', str(Path(__file__).parents[1] / 'research' / 'isolated_guard.py')))


def api():
    assert MODULE.exists(), 'isolated guard API must exist'
    spec = importlib.util.spec_from_file_location('guard_test', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(run):
    return {'status': 'verified', 'run_root': str(run),
            'python_executable': str(run / 'python' / 'python.exe')}


def test_environment_does_not_inherit_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'must-never-copy')
    monkeypatch.setenv('PYTHONPATH', 'outside')
    env = api().build_environment(tmp_path, manifest(tmp_path))
    assert 'OPENAI_API_KEY' not in env and 'PYTHONPATH' not in env
    assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1'
    if os.name == 'nt':
        assert env['SystemRoot'] == env['WINDIR'] == 'C:\\Windows'
    for key in ('HOME', 'USERPROFILE', 'TEMP', 'TMP', 'HF_HOME', 'TORCH_HOME'):
        assert Path(env[key]).is_relative_to(tmp_path)


def test_binding_and_unsafe_writes(tmp_path):
    module = api()
    bad = manifest(tmp_path)
    bad['run_root'] = str(tmp_path.parent)
    with pytest.raises(ValueError):
        module.build_environment(tmp_path, bad)
    with pytest.raises(ValueError):
        module.validate_write_path(tmp_path, tmp_path / '..' / 'escape')
    source = tmp_path / 'source'
    source.write_text('x')
    os.link(source, tmp_path / 'alias')
    with pytest.raises(ValueError):
        module.validate_write_path(tmp_path, source)


@pytest.mark.parametrize('operation', [
    "socket.socket()", "socket.getaddrinfo('example.invalid', 80)",
    "subprocess.run([sys.executable, '-c', 'pass'])", "os.system('never_execute')",
    "open(outside, 'w')", "os.mkdir(outside)", "os.rename(inside, outside)",
    "ctypes.CDLL(outside)", "site.addsitedir(outside)",
    "os.remove(outside)", "os.link(inside, outside)",
])
def test_hook_blocks_in_fresh_child(tmp_path, operation):
    api()
    run = tmp_path / 'run'
    run.mkdir()
    inside = run / 'inside'
    inside.write_text('fixture')
    outside = tmp_path / 'outside'
    script = '''import importlib.util,json,sys,os,socket,subprocess,ctypes,site
spec=importlib.util.spec_from_file_location('guard',sys.argv[1]); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
run=sys.argv[2]; inside=sys.argv[3]; outside=sys.argv[4]
m.install_guard(run,json.loads(sys.argv[5]))
try:
 exec(sys.argv[6])
except (PermissionError,ValueError):
 print('BLOCKED')
else:
 raise AssertionError('operation was allowed')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(MODULE), str(run),
                             str(inside), str(outside), json.dumps(manifest(run)), operation],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'BLOCKED'
    assert not outside.exists()


def test_hook_allows_snapshot_write(tmp_path):
    module = api()
    assert module.validate_write_path(tmp_path, tmp_path / 'new') == tmp_path / 'new'


def test_environment_rejects_nonstandard_windows_root(tmp_path, monkeypatch):
    if os.name != 'nt':
        pytest.skip('Windows environment gate')
    monkeypatch.setenv('SystemRoot', str(tmp_path))
    with pytest.raises(ValueError):
        api().build_environment(tmp_path, manifest(tmp_path))


@pytest.mark.parametrize('operation', [
    "open(os.path.join(run, '.env'), 'r')",
    "open(os.path.join(run, '.env.local'), 'rb')",
])
def test_secret_reads_are_blocked_before_open(tmp_path, operation):
    test_hook_blocks_in_fresh_child(tmp_path, operation)


def test_named_existing_system_dll_allowed_in_fresh_child(tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows DLL gate')
    api()
    script = '''import importlib.util,json,sys,ctypes
spec=importlib.util.spec_from_file_location('guard',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.install_guard(sys.argv[2],json.loads(sys.argv[3]))
ctypes.WinDLL('kernel32.dll')
print('ALLOWED')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(MODULE),
                             str(tmp_path), json.dumps(manifest(tmp_path))],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'ALLOWED'
