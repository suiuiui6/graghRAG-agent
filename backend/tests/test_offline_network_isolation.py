"""Offline research guards must not alter networking during test collection."""
import importlib
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest


@pytest.mark.parametrize("name", ["test_development_structure", "test_development_scope"])
def test_imports_preserve_socket_methods(name):
    code = (
        "import socket, importlib; "
        "original=(socket.socket.connect,socket.create_connection); "
        f"importlib.import_module('tests.{name}'); "
        "assert original==(socket.socket.connect,socket.create_connection); "
        "a,b=socket.socketpair(); a.close(); b.close()"
    )
    env = dict(os.environ, PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", ["test_development_structure", "test_development_scope"])
def test_offline_fixture_denies_then_restores(name):
    module = importlib.import_module(f"tests.{name}")
    original = socket.socket.connect, socket.create_connection
    with pytest.MonkeyPatch.context() as patch:
        module.offline_network.__wrapped__(patch)
        with pytest.raises(AssertionError, match="测试禁止网络"):
            socket.create_connection(("127.0.0.1", 9))
        with socket.socket() as connection:
            with pytest.raises(AssertionError, match="测试禁止网络"):
                connection.connect(("127.0.0.1", 9))
    assert original == (socket.socket.connect, socket.create_connection)
