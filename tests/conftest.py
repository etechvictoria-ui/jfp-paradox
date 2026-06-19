"""Shared fixtures for JFP test suite."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

DAEMON_DIR = Path(__file__).resolve().parent.parent / "daemon"
VENV_PYTHON = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _rpc(socket_path: str, method: str, params: dict | None = None, token: str = "") -> dict:
    req = {
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
        "session_token": token,
    }
    addr = ("\0" + socket_path[1:]) if socket_path.startswith("@") else socket_path
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(addr)
    s.sendall(json.dumps(req).encode("utf-8"))
    raw = s.recv(65536)
    s.close()
    return json.loads(raw.decode("utf-8"))


@pytest.fixture()
def tmp_log(tmp_path):
    """Return a temporary JSONL log path."""
    return str(tmp_path / "jfp_proof.jsonl")


@pytest.fixture()
def live_daemon(tmp_path):
    """Start a live daemon subprocess; yield (socket_path, rpc_fn); teardown kills it."""
    socket_path = f"@jfpd_test_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    log_path = str(tmp_path / "jfp_proof.jsonl")

    env = {
        **os.environ,
        "JFP_DRY_RUN": "1",
        "JFP_LOG_PATH": log_path,
        "JFP_SOCKET_PATH": socket_path,
        "JFP_OPERATOR_TOKEN": "test-token",
        "JFP_SIGNING_ENABLED": "0",
    }

    proc = subprocess.Popen(
        [PYTHON, "jfpd.py"],
        cwd=str(DAEMON_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for daemon to be ready (up to 5s)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            resp = _rpc(socket_path, "health.ping")
            if resp.get("ok"):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        proc.wait()
        pytest.fail("Daemon did not become ready in time")

    def rpc(method, params=None, token=""):
        return _rpc(socket_path, method, params, token)

    yield socket_path, log_path, rpc

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
