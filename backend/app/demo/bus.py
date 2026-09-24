"""In-process pub/sub for demo events.

The demo agent runs one tool at a time and calls `publish(run_id, event)`.
Every WebSocket connected to that run_id receives the event immediately.

For a single-process demo, this is enough. In production you'd swap this
for Redis pub/sub (Redis is already a dependency) so multiple backend
workers can serve the same run.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class RunBus:
    """One bus per run_id. Broadcasts events to N WebSocket subscribers."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subs[run_id].add(q)
        return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subs[run_id].discard(q)
            if not self._subs[run_id]:
                self._subs.pop(run_id, None)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subs.get(run_id, ()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("demo.bus.drop run_id=%s (queue full)", run_id)

    async def close(self, run_id: str) -> None:
        """Signal completion by pushing a sentinel to every subscriber."""
        async with self._lock:
            queues = list(self._subs.get(run_id, ()))
        for q in queues:
            try:
                q.put_nowait({"__done__": True})
            except asyncio.QueueFull:
                pass


bus = RunBus()