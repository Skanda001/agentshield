"""Cryptographic primitives for the audit chain."""
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable JSON for hashing: sorted keys, no whitespace, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hmac_sha256_hex(data: str, secret: str | None = None) -> str:
    key = (secret or settings.AUDIT_HMAC_SECRET).encode("utf-8")
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()


def compute_event_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    """Compute the chain hash for an audit event.

    hash = SHA256(prev_hash + canonical_json(payload))

    The HMAC signature is computed separately for tamper detection.
    """
    material = f"{prev_hash}:{canonical_json(payload)}"
    return sha256_hex(material)


def sign_hash(chain_hash: str) -> str:
    """HMAC-SHA256 over the chain hash, keyed with AUDIT_HMAC_SECRET."""
    return hmac_sha256_hex(chain_hash)


def verify_signature(chain_hash: str, signature: str) -> bool:
    expected = sign_hash(chain_hash)
    return hmac.compare_digest(expected, signature)