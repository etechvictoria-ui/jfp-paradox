from __future__ import annotations

import json
import os
import socket
import time
import uuid
from typing import Any, Dict


class JFPClient:
    def __init__(self, socket_path: str | None = None, token: str | None = None) -> None:
        self.socket_path = socket_path or os.getenv("JFP_SOCKET_PATH", "/run/jfpd.sock")
        self.token = token or os.getenv("JFP_OPERATOR_TOKEN", "local-dev-token")

    def call(self, method: str, params: Dict[str, Any] | None = None, with_token: bool = False) -> Dict[str, Any]:
        req = {
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
            "session_token": self.token if with_token else "",
        }
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    if self.socket_path.startswith("@"):
                        client.connect("\0" + self.socket_path[1:])
                    else:
                        client.connect(self.socket_path)
                    client.sendall(json.dumps(req).encode("utf-8"))
                    raw = client.recv(65536)
                return json.loads(raw.decode("utf-8"))
            except OSError as exc:
                last_exc = exc
                # Retry transient startup races (connection refused / no such endpoint).
                if getattr(exc, "errno", None) in (2, 111):
                    time.sleep(0.15)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("RPC call failed without exception")
