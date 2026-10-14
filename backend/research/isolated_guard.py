"""Supplemental audit guard for trusted, bounded capture code.

This is not a native-code sandbox and never substitutes for the verified OS
firewall. Install only in the disposable unprivileged child before service
imports. Native extensions and unaudited operations require separate review.
"""
from __future__ import annotations

import os
from pathlib import Path
import site
import stat
import sys


def _absolute(path):
    return Path(os.path.abspath(os.fsdecode(path)))


def _safe(path, allow_hardlinks=False):
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('unsafe reparse/link path')
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1 and not allow_hardlinks:
            raise ValueError('unsafe hardlink path')
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('unsupported filesystem object')


def validate_write_path(run_root, path):
    """Lexical containment plus ancestor identity checks; no resolution through links."""
    root, target = _absolute(run_root), _absolute(path)
    _safe(root)
    if not target.is_relative_to(root):
        raise ValueError('write escapes snapshot')
    _safe(target)
    return target


def _binding(run_root, manifest):
    root = _absolute(run_root)
    _safe(root)
    if (manifest.get('status') != 'verified'
            or _absolute(manifest.get('run_root', '')) != root
            or _absolute(manifest.get('python_executable', '')) != root / 'python' / 'python.exe'):
        raise ValueError('snapshot manifest binding mismatch')
    return root


def _windows_root():
    """Accept only the explicitly supported Windows installation directory."""
    expected = Path('C:/Windows')
    for key in ('SystemRoot', 'WINDIR'):
        value = os.environ.get(key)
        if value and _absolute(value) != expected:
            raise ValueError('unsupported Windows system directory')
    _safe(expected)
    if not expected.is_dir() or not (expected / 'System32').is_dir():
        raise ValueError('Windows system directory missing')
    return expected


def build_environment(run_root, manifest):
    """Return a fresh allowlist; no os.environ values or credentials are copied."""
    root = _binding(run_root, manifest)
    paths = {'HOME': root / 'home', 'USERPROFILE': root / 'home',
             'APPDATA': root / 'home' / 'AppData' / 'Roaming',
             'LOCALAPPDATA': root / 'home' / 'AppData' / 'Local',
             'TEMP': root / 'tmp', 'TMP': root / 'tmp',
             'HF_HOME': root / 'cache' / 'huggingface',
             'HF_HUB_CACHE': root / 'cache' / 'huggingface' / 'hub',
             'TRANSFORMERS_CACHE': root / 'cache' / 'huggingface' / 'hub',
             'TORCH_HOME': root / 'cache' / 'torch',
             'XDG_CACHE_HOME': root / 'cache', 'NUMBA_CACHE_DIR': root / 'cache' / 'numba',
             'MPLCONFIGDIR': root / 'cache' / 'matplotlib'}
    for path in paths.values():
        validate_write_path(root, path).mkdir(parents=True, exist_ok=True)
    windows = {'SystemRoot': str(_windows_root()), 'WINDIR': str(_windows_root())} if os.name == 'nt' else {}
    return {**windows, **{key: str(value) for key, value in paths.items()},
            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
            'HF_DATASETS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
            'DO_NOT_TRACK': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONNOUSERSITE': '1', 'TOKENIZERS_PARALLELISM': 'false'}


def install_guard(run_root, manifest):
    """Install irreversible supplemental restrictions in the disposable child.

    Caller first verifies executable/hash/receipt and -I -S -B, sanitizes sys.path
    and environment, and establishes the process-specific OS firewall. This
    helper validates manifest paths only; it does not attest those launch gates.
    """
    root = _binding(run_root, manifest)
    counters = {'blocked': 0}
    # Small explicit native-loader exceptions, not arbitrary System32 access.
    system_dlls = {}
    if os.name == 'nt':
        system32 = _windows_root() / 'System32'
        for name in ('kernel32.dll', 'msvcrt.dll', 'ucrtbase.dll', 'advapi32.dll',
                     'user32.dll', 'ole32.dll', 'shell32.dll', 'bcrypt.dll', 'ntdll.dll'):
            path = system32 / name
            _safe(path, allow_hardlinks=True)  # Windows servicing uses hardlinks.
            if path.is_file():
                system_dlls[name] = path

    def native_path(value):
        if value is None:
            raise ValueError('anonymous native handle denied')
        decoded = os.fsdecode(value)
        if decoded.lower() in system_dlls:
            return system_dlls[decoded.lower()]
        path = _absolute(decoded)
        if path in system_dlls.values():
            _safe(path, allow_hardlinks=True)
            return path
        return validate_write_path(root, path)

    # Force allowed short DLL names to absolute system paths before the loader;
    # otherwise application-directory search could shadow an allowed name.
    import ctypes
    original_dlopen = ctypes._dlopen

    def bounded_dlopen(name, *args, **kwargs):
        try:
            path = native_path(name)
        except (ValueError, TypeError, OSError):
            deny()
        return original_dlopen(str(path), *args, **kwargs)

    ctypes._dlopen = bounded_dlopen

    def deny(*args, **kwargs):
        counters['blocked'] += 1
        raise PermissionError('isolated capture operation blocked')

    def write(path, dir_fd=None):
        if dir_fd not in (None, -1):
            deny()
        try:
            validate_write_path(root, path)
        except (ValueError, TypeError, OSError):
            deny()

    mutations = {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown',
                 'os.utime', 'os.truncate', 'os.setxattr', 'os.removexattr'}

    def audit(event, args):
        if event == 'sqlite3.connect':
            # SQLite writes through native code rather than Python's open audit.
            # URI modes and temporary unnamed databases have alternate path or
            # temp-directory semantics, so deny them rather than guess scope.
            database = args[0]
            if isinstance(database, int):
                deny()
            try:
                name = os.fsdecode(database)
            except (TypeError, ValueError):
                deny()
            if name != ':memory:':
                if not name or name.lower().startswith('file:'):
                    deny()
                write(name)
        if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn'))
                or event in {'os.system', 'os.fork', 'os.forkpty', 'os.startfile',
                             'os.startfile/2', 'os.link', 'os.symlink'}):
            deny()
        if event == 'open':
            path, mode, flags = args
            if not isinstance(path, int) and any(part.lower().startswith('.env') for part in Path(os.fsdecode(path)).parts):
                deny()
            if (mode and any(char in mode for char in 'wax+')) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                write(path)
        elif event == 'os.rename':
            write(args[0], args[2] if len(args) > 2 else None)
            write(args[1], args[3] if len(args) > 3 else None)
        elif event in mutations:
            # CPython uses the last field as dir_fd for these events, except truncate/xattrs.
            fd = args[-1] if event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown', 'os.utime'} else None
            write(args[0], fd)
        elif event == 'ctypes.dlopen':
            try:
                native_path(args[0])
            except (ValueError, TypeError, OSError):
                deny()
        elif event == 'import' and len(args) > 1 and args[1]:
            filename = str(args[1])
            if filename.lower().endswith(('.pyd', '.dll', '.so')):
                try:
                    validate_write_path(root, filename)
                except (ValueError, TypeError, OSError):
                    deny()

    site.addsitedir = deny
    site.addpackage = deny
    sys.addaudithook(audit)
    return counters
