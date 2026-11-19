"""Redis-backed sliding-window rate limiter.

Fail policy: FAIL OPEN — if Redis is unreachable the request is allowed through.
This is deliberate: a Redis outage should not take down the gateway itself.
The tradeoff is documented here and in docs/threat-model.md.

Usage (FastAPI dependency)::

    from app.core.rate_limit import rate_limit

    @router.post("/agents/token")
    async def issue_token(
        request: Request,
        _: None = Depends(rate_limit("token", max_calls=10, window_seconds=60)),
        ...
    ):
        ...
"""
import time
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level pool — created once at first use
_pool: Optional[aioredis.Redis] = None


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return the shared Redis connection; return None on connection failure."""
    global _pool
    if _pool is None:
        try:
            _pool = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception as exc:
            logger.warning("rate_limit: Redis pool creation failed — failing open: %s", exc)
            return None
    return _pool


def rate_limit(key_prefix: str, max_calls: int, window_seconds: int):
    """Return a FastAPI dependency that enforces a sliding-window rate limit.

    Key  : ``rl:{key_prefix}:{client_ip}``
    Uses : Redis INCR + EXPIRE (atomic enough for a soft limit).
    On Redis failure: fail OPEN (request allowed, warning logged).

    Args:
        key_prefix: Logical name for the limit (e.g. "token", "decide").
        max_calls: Maximum requests allowed in the window.
        window_seconds: Length of the sliding window in seconds.
    """
    async def _dependency(request: Request) -> None:
        # Identify client: prefer forwarded IP (behind reverse proxy), fallback to direct
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        redis = await _get_redis()
        if redis is None:
            # Fail open: Redis down → allow request
            logger.warning("rate_limit: Redis unavailable, failing open for %s/%s", key_prefix, client_ip)
            return

        redis_key = f"rl:{key_prefix}:{client_ip}"
        try:
            count = await redis.incr(redis_key)
            if count == 1:
                # First call in this window — set the expiry
                await redis.expire(redis_key, window_seconds)

            if count > max_calls:
                # Read the remaining TTL so we can report it in Retry-After
                ttl = await redis.ttl(redis_key)
                retry_after = max(ttl, 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit exceeded: max {max_calls} requests "
                        f"per {window_seconds}s. Retry after {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Any Redis error → fail open
            logger.warning("rate_limit: Redis error, failing open: %s", exc)

    return _dependency
