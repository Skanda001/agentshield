"""HTTP client for AgentShield."""
import os
from typing import Any, Optional

import httpx

from shield.exceptions import ShieldConfigError, ShieldError
from shield.models import Decision


DEFAULT_API_URL = "http://localhost:8001"
TIMEOUT_SECONDS = 10.0


class ShieldClient:
    """Client used by the @protect decorator. Reads env vars by default.

    env:
      AGENTSHIELD_API_URL   (default: http://localhost:8001)
      AGENTSHIELD_API_KEY   (required)
    """

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self.api_url = (api_url or os.getenv("AGENTSHIELD_API_URL") or DEFAULT_API_URL).rstrip("/")
        self.api_key = api_key or os.getenv("AGENTSHIELD_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise ShieldConfigError(
                "AGENTSHIELD_API_KEY is not set. "
                "Export it or pass api_key= to ShieldClient()."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }

    def _token(self) -> str:
        # For simplicity the SDK exchanges the API key for a JWT on first use
        # and reuses it. Real SDKs cache + refresh; Tier 1 keeps it simple.
        cache = getattr(self, "_cached_token", None)
        if cache:
            return cache

        url = f"{self.api_url}/api/v1/agents/token"
        try:
            r = httpx.post(url, json={"api_key": self.api_key}, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ShieldError(f"Failed to reach AgentShield at {url}: {e}") from e

        if r.status_code != 200:
            raise ShieldError(f"Token exchange failed: {r.status_code} {r.text}")

        token = r.json().get("access_token")
        if not token:
            raise ShieldError("Token response missing access_token")

        self._cached_token = token
        return token

    def decide(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        resource_type: Optional[str] = None,
        data_classification: Optional[str] = None,
    ) -> Decision:
        url = f"{self.api_url}/api/v1/decide"
        body = {
            "tool": tool,
            "arguments": arguments,
            "resource_type": resource_type,
            "data_classification": data_classification,
        }
        try:
            r = httpx.post(url, json=body, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ShieldError(f"AgentShield unreachable: {e}") from e

        if r.status_code == 401:
            # Token expired — drop cache and retry once.
            self._cached_token = None
            r = httpx.post(url, json=body, headers=self._headers(), timeout=self.timeout)

        if r.status_code != 200:
            raise ShieldError(f"Decision request failed: {r.status_code} {r.text}")

        return Decision.from_dict(r.json())