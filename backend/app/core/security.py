"""Security primitives: JWT tokens and API key hashing."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


# ─── API key generation & hashing ─────────────────────────────

def generate_api_key() -> str:
    """Generate a URL-safe API key. Shown to the user exactly once."""
    return "ash_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key with HMAC-SHA256 using the JWT secret as the HMAC key.

    We use HMAC (not bcrypt) because:
    - API keys are 43-char high-entropy strings, not guessable passwords.
    - We need to look them up by hash on every request (must be fast).
    - A fixed HMAC key means a stolen DB cannot be brute-forced offline.
    """
    return hmac.new(
        settings.API_KEY_HMAC_SECRET.encode(),
        api_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# ─── JWT ──────────────────────────────────────────────────────

def create_agent_token(
    *,
    agent_id: str,
    tenant_id: str,
    scopes: list[str],
    expires_minutes: Optional[int] = None,
) -> str:
    """Create a short-lived access token for an authenticated agent."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.AGENTSHIELD_ACCESS_TOKEN_MINUTES
    )
    payload: Dict[str, Any] = {
        "sub": agent_id,
        "tenant_id": tenant_id,
        "scopes": scopes,
        "type": "agent_access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.AGENTSHIELD_JWT_SECRET,
        algorithm=settings.AGENTSHIELD_JWT_ALGORITHM,
    )


def decode_agent_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode an agent access token. Returns None on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.AGENTSHIELD_JWT_SECRET,
            algorithms=[settings.AGENTSHIELD_JWT_ALGORITHM],
        )
    except InvalidTokenError:
        return None

    if payload.get("type") != "agent_access":
        return None
    return payload