"""Periodic audit chain verification.

Runs as a background task. Every N minutes, walks the chain and logs
whether it's still valid. If it fails, it logs at ERROR level (which
would trigger alerting in production).
"""
import asyncio
import logging
from typing import Optional

from app.audit.verifier import verify_chain
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 15 * 60   # 15 minutes


async def verify_once() -> bool:
    async with AsyncSessionLocal() as db:
        result = await verify_chain(db)

    if result.valid:
        logger.info(
            "audit.verify.ok",
            extra={"verified": result.verified_events, "total": result.total_events},
        )
        return True

    logger.error(
        "audit.verify.failed",
        extra={
            "broken_at_seq": result.broken_at_seq,
            "reason": result.reason,
        },
    )
    return False


async def periodic_verifier(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Loop: verify, sleep, repeat. Stops if stop_event is set."""
    while True:
        try:
            await verify_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("audit.verify.error: %s", e)

        if stop_event is not None and stop_event.is_set():
            return

        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                return
            await asyncio.sleep(interval_seconds)
        except asyncio.TimeoutError:
            pass