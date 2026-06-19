import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except Exception:  # pragma: no cover
    serialization = None
    Ed25519PrivateKey = None


class ProofLogger:
    def __init__(self, log_path: str, seed_hash: str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.prev_hash = seed_hash
        self.counter = 0
        self.signing_enabled = os.getenv("JFP_SIGNING_ENABLED", "0") == "1"
        self.signing_key_path = os.getenv("JFP_SIGNING_KEY", "")
        self.private_key = self._load_private_key() if self.signing_enabled else None
        self.pubkey_id = self._derive_pubkey_id() if self.private_key else ""
        self._recover_tail_hash()

    def _recover_tail_hash(self) -> None:
        if not self.log_path.exists():
            return
        last_line = ""
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line.strip()
        if not last_line:
            return
        try:
            obj = json.loads(last_line)
            tail_hash = obj.get("entry_hash")
            if isinstance(tail_hash, str) and tail_hash:
                self.prev_hash = tail_hash
            counter = obj.get("counter")
            if isinstance(counter, int):
                self.counter = max(0, counter + 1)
        except json.JSONDecodeError:
            return

    def _load_private_key(self) -> Any:
        if Ed25519PrivateKey is None or serialization is None:
            raise RuntimeError("JFP signing enabled but cryptography package is not available")
        if not self.signing_key_path:
            raise RuntimeError("JFP signing enabled but JFP_SIGNING_KEY is not set")
        key_path = Path(self.signing_key_path)
        if not key_path.exists():
            raise RuntimeError(f"JFP signing key not found: {self.signing_key_path}")
        key_data = key_path.read_bytes()
        private = serialization.load_pem_private_key(key_data, password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise RuntimeError("JFP signing key must be Ed25519 private key")
        return private

    def _derive_pubkey_id(self) -> str:
        if self.private_key is None or serialization is None:
            return ""
        pub = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(pub).hexdigest()[:16]

    @staticmethod
    def _canonical_json(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _sign_entry_hash(self, entry_hash: str) -> str:
        if self.private_key is None:
            return ""
        sig = self.private_key.sign(entry_hash.encode("utf-8"))
        return base64.b64encode(sig).decode("ascii")

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        base_record = dict(record)
        base_record["counter"] = self.counter
        base_record["mono_ns"] = time.monotonic_ns()
        base_record["prev_hash"] = self.prev_hash
        canonical = self._canonical_json(base_record)
        entry_hash = hashlib.sha256((self.prev_hash + canonical).encode("utf-8")).hexdigest()
        base_record["entry_hash"] = entry_hash
        if self.private_key is not None:
            base_record["pubkey_id"] = self.pubkey_id
            base_record["signature"] = self._sign_entry_hash(entry_hash)

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(self._canonical_json(base_record) + "\n")

        self.prev_hash = entry_hash
        self.counter += 1
        return base_record
