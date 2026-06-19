#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:
    serialization = None
    Ed25519PublicKey = None


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_records(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {idx}: invalid JSON ({exc})") from exc
    return rows


def load_pubkey(path: Path) -> Any:
    if serialization is None or Ed25519PublicKey is None:
        raise RuntimeError("cryptography package is required for signature verification")
    data = path.read_bytes()
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError("public key is not Ed25519")
    return key


def verify(path: Path, seed_hash: str, pubkey: Any | None) -> int:
    rows = load_records(path)
    if not rows:
        print("FAIL: empty log")
        return 1
    prev = seed_hash
    prev_counter = -1
    for idx, row in enumerate(rows, start=1):
        if "entry_hash" not in row:
            print(f"FAIL line {idx}: missing entry_hash")
            return 1
        if "prev_hash" not in row:
            print(f"FAIL line {idx}: missing prev_hash")
            return 1
        if row["prev_hash"] != prev:
            print(f"FAIL line {idx}: prev_hash mismatch")
            return 1

        counter = row.get("counter")
        if not isinstance(counter, int):
            print(f"FAIL line {idx}: counter missing or invalid")
            return 1
        if counter <= prev_counter:
            print(f"FAIL line {idx}: counter not monotonic")
            return 1

        base = dict(row)
        entry_hash = str(base.pop("entry_hash"))
        signature = base.pop("signature", None)
        base.pop("pubkey_id", None)
        recomputed = hashlib.sha256((row["prev_hash"] + canonical_json(base)).encode("utf-8")).hexdigest()
        if recomputed != entry_hash:
            print(f"FAIL line {idx}: entry_hash mismatch")
            return 1

        if pubkey is not None:
            if not isinstance(signature, str) or not signature:
                print(f"FAIL line {idx}: missing signature")
                return 1
            try:
                sig_bytes = base64.b64decode(signature.encode("ascii"))
                pubkey.verify(sig_bytes, entry_hash.encode("utf-8"))
            except Exception as exc:
                print(f"FAIL line {idx}: signature invalid ({exc})")
                return 1

        prev = entry_hash
        prev_counter = counter

    print(f"PASS: chain_valid records={len(rows)} signed={'yes' if pubkey else 'no'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify JFP proof chain integrity")
    parser.add_argument("log_path", type=Path, help="Path to jfp_proof.jsonl")
    parser.add_argument("--seed-hash", default="0" * 64, help="Expected seed prev_hash")
    parser.add_argument("--pubkey", type=Path, default=None, help="Ed25519 public key PEM")
    args = parser.parse_args()

    pubkey = load_pubkey(args.pubkey) if args.pubkey else None
    return verify(args.log_path, args.seed_hash, pubkey)


if __name__ == "__main__":
    sys.exit(main())

