"""Guard callback unit tests complement the existing real child-process tests.

Registration and native loading are intercepted; validation and callback bodies
are real. No irreversible hook is installed in the pytest process.
"""
import ctypes
import importlib.util
import os
import site
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def module():
    source = Path(__file__).parents[1] / 'research/isolated_guard.py'
    spec = importlib.util.spec_from_file_location('readiness_guard', source)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def binding(root):
    return {'status': 'verified', 'run_root': str(root),
            'python_executable': str(root / 'python/python.exe')}


@pytest.fixture
def guard(tmp_path, monkeypatch):
    m = module()
    hooks, loaded = [], []
    monkeypatch.setattr(sys, 'addaudithook', hooks.append)
    monkeypatch.setattr(ctypes, '_dlopen', lambda name, *args, **kwargs: loaded.append(name) or 42)
    monkeypatch.setattr(site, 'addsitedir', site.addsitedir)
    monkeypatch.setattr(site, 'addpackage', site.addpackage)
    counters = m.install_guard(tmp_path, binding(tmp_path))
    assert len(hooks) == 1
    return m, hooks[0], counters, tmp_path, loaded


@pytest.mark.parametrize('event,args', [
    ('socket.connect', ()), ('subprocess.Popen', ()), ('os.exec', ()), ('os.spawn', ()),
    ('os.posix_spawn', ()), ('os.system', ()), ('os.fork', ()), ('os.forkpty', ()),
    ('os.startfile', ()), ('os.startfile/2', ()), ('os.link', ()), ('os.symlink', ()),
])
def test_network_process_and_link_events_are_denied_and_counted(guard, event, args):
    _, audit, counts, _, _ = guard
    with pytest.raises(PermissionError):
        audit(event, args)
    assert counts['blocked'] == 1


@pytest.mark.parametrize('database', [0, None, b'', '', 'file:relative.db', b'FILE:relative.db'])
def test_sqlite_special_paths_are_denied(guard, database):
    _, audit, counts, _, _ = guard
    with pytest.raises(PermissionError):
        audit('sqlite3.connect', (database,))
    assert counts['blocked'] == 1


def test_sqlite_and_normal_reads_within_snapshot_are_allowed(guard):
    _, audit, counts, root, _ = guard
    audit('sqlite3.connect', (':memory:',))
    audit('sqlite3.connect', (root / 'local.sqlite3',))
    audit('open', (root / 'file', 'w', os.O_WRONLY))
    audit('open', (root.parent / 'ordinary.txt', 'r', os.O_RDONLY))
    audit('open', (1, 'r', os.O_RDONLY))
    audit('import', ('package', str(root.parent / 'normal.py')))
    audit('unrelated.event', ())
    assert counts['blocked'] == 0


@pytest.mark.parametrize('mode,flags', [('w', 0), ('r+', 0), (None, os.O_CREAT),
                                      (None, os.O_RDWR), (None, os.O_TRUNC), (None, os.O_APPEND)])
def test_all_write_modes_and_flags_reject_outside_snapshot(guard, mode, flags):
    _, audit, counts, root, _ = guard
    with pytest.raises(PermissionError):
        audit('open', (root.parent / 'outside', mode, flags))
    assert counts['blocked'] == 1


@pytest.mark.parametrize('event', ['os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown',
                                  'os.utime', 'os.truncate', 'os.setxattr', 'os.removexattr'])
def test_mutation_events_validate_paths_without_performing_mutation(guard, event):
    _, audit, counts, root, _ = guard
    audit(event, (root / 'inside', None))
    with pytest.raises(PermissionError):
        audit(event, (root.parent / 'outside', None))
    assert counts['blocked'] == 1


def test_directory_descriptors_rename_and_env_reads_are_denied(guard):
    _, audit, counts, root, _ = guard
    for event, args in [('os.mkdir', (root / 'inside', 0o700, 3)),
                        ('os.rename', (root / 'a', root.parent / 'b', -1, -1)),
                        ('os.rename', (root / 'a', root / 'b', 3, -1)),
                        ('open', (root / '.ENV.local', 'r', 0))]:
        with pytest.raises(PermissionError):
            audit(event, args)
    audit('os.rename', (root / 'a', root / 'b'))
    # CPython rejects a None filename before a real open audit event is emitted.
    with pytest.raises(TypeError):
        audit('open', (None, 'w', 0))
    assert counts['blocked'] == 4


def test_native_load_and_extension_import_validate_paths(guard):
    _, audit, counts, root, loaded = guard
    for name in [None, root.parent / 'foreign.dll', object()]:
        with pytest.raises(PermissionError):
            ctypes._dlopen(name)
    assert ctypes._dlopen(root / 'trusted.dll') == 42
    assert loaded == [str(root / 'trusted.dll')]
    audit('ctypes.dlopen', (root / 'trusted.dll',))
    audit('import', ('extension', str(root / 'trusted.pyd')))
    for event, args in [('ctypes.dlopen', (None,)),
                        ('import', ('extension', str(root.parent / 'foreign.pyd')))]:
        with pytest.raises(PermissionError):
            audit(event, args)
    assert counts['blocked'] == 5


def test_site_injection_is_disabled(guard):
    _, _, counts, root, _ = guard
    for operation in (site.addsitedir, site.addpackage):
        with pytest.raises(PermissionError):
            operation(str(root))
    assert counts['blocked'] == 2


def test_nonwindows_environment_does_not_copy_windows_or_secrets(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, 'os', SimpleNamespace(**{**vars(os), 'name': 'posix'}))
    env = m.build_environment(tmp_path, binding(tmp_path))
    assert 'SystemRoot' not in env and 'WINDIR' not in env and 'PATH' not in env
    assert env['HF_HUB_OFFLINE'] == '1' and env['PYTHONNOUSERSITE'] == '1'


def test_manifest_identity_is_strict_and_hardlinks_can_only_be_explicitly_allowed(tmp_path):
    m = module()
    for field, value in [('status', 'pending'), ('python_executable', str(tmp_path / 'bad.exe'))]:
        with pytest.raises(ValueError):
            m.build_environment(tmp_path, {**binding(tmp_path), field: value})
    original = tmp_path / 'file'
    original.write_bytes(b'safe fixture')
    os.link(original, tmp_path / 'alias')
    with pytest.raises(ValueError):
        m._safe(original)
    m._safe(original, allow_hardlinks=True)


@pytest.mark.parametrize('mode,attributes', [(stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400), (stat.S_IFIFO, 0)])
def test_reparse_link_and_unsupported_filesystem_objects_are_rejected(tmp_path, monkeypatch, mode, attributes):
    m = module()
    target = tmp_path / 'untrusted-object'
    real_lstat = Path.lstat
    def filesystem_stat(path, *args, **kwargs):
        if path == target:
            return SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_nlink=1)
        return real_lstat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', filesystem_stat)
    with pytest.raises(ValueError):
        m.validate_write_path(tmp_path, target)


def test_named_system_dlls_are_bound_to_absolute_paths_before_loader(guard):
    _, audit, counts, _, loaded = guard
    assert ctypes._dlopen('kernel32.dll') == 42
    assert Path(loaded[-1]) == Path('C:/Windows/System32/kernel32.dll')
    assert ctypes._dlopen('C:/Windows/System32/kernel32.dll') == 42
    audit('ctypes.dlopen', ('kernel32.dll',))
    assert counts['blocked'] == 0
