"""Periodic worker: expire pending approvals past their deadline."""
import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.approval_service import expire_stale

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 60


async def expire_once() -> int:
    async with AsyncSessionLocal() as db:
        count = await expire_stale(db)
    if count:
        logger.info("approvals.expired: %d", count)
    return count


async def periodic_expirer(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    stop_event: asyncio.Event | None = None,
) -> None:
    while True:
        try:
            await expire_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("approvals.expire.error: %s", e)

        if stop_event is not None and stop_event.is_set():
            return
        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                return
            await asyncio.sleep(interval_seconds)
        except asyncio.TimeoutError:
            pass