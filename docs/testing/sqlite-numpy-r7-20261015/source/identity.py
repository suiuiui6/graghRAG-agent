"""Local runtime and installed NumPy identity; no providers or external IO."""
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sqlite3
import ssl
import sys

import numpy as np


def file_identity(path):
    p = Path(path)
    return {"path": str(p), "size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


np.dot(np.ones((4,4)), np.ones((4,4)))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    np.show_config()
con = sqlite3.connect(":memory:")
sqlite = {"version": sqlite3.sqlite_version, "source_id": con.execute("SELECT sqlite_source_id()").fetchone()[0], "compile_options": [row[0] for row in con.execute("PRAGMA compile_options")]}
con.close()
numpy_root = Path(np.__file__).parent
native = sorted(set(numpy_root.rglob("*.pyd")) | set(numpy_root.rglob("*.dll")) | set(numpy_root.parent.glob("numpy.libs/*.dll")))
loaded = []
if os.name == "nt":
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    modules = (wintypes.HMODULE*2048)()
    needed = wintypes.DWORD()
    process = kernel32.GetCurrentProcess()
    if not psapi.EnumProcessModules(process, modules, ctypes.sizeof(modules), ctypes.byref(needed)):
        raise ctypes.WinError(ctypes.get_last_error())
    if needed.value > ctypes.sizeof(modules):
        raise RuntimeError("module inventory truncated")
    for handle in modules[:needed.value//ctypes.sizeof(wintypes.HMODULE)]:
        name = ctypes.create_unicode_buffer(32768)
        if not psapi.GetModuleFileNameExW(process, handle, name, len(name)):
            raise ctypes.WinError(ctypes.get_last_error())
        loaded.append(file_identity(name.value))
result = {"python":sys.version,"executable":str(Path(sys.executable).resolve()),"base_prefix":sys.base_prefix,"platform":platform.platform(),"sqlite":sqlite,"openssl":ssl.OPENSSL_VERSION,"installed":[{"name": d.metadata["Name"],"version":d.version} for d in importlib.metadata.distributions()],"numpy_config":buf.getvalue(),"numpy_native_files":[file_identity(p) for p in native],"actual_loaded_modules":loaded,"limitations":"Build/config and loaded DLL hashes are identity evidence, not complete SBOM or native vulnerability scan."}
print(json.dumps(result,indent=2,ensure_ascii=False))
