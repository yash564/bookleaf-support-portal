"""In-process pub/sub for near-real-time ticket updates.

Services publish lightweight *signals* ("ticket #1003 changed"); SSE subscribers forward them to the
browser, which then refetches via the normal REST endpoints. Keeping payloads tiny means there is
exactly one serialization path (the REST schemas) and nothing can go stale between the two.

Single-process by design for this assignment. For multiple backend instances, swap the dict of
queues for Redis pub/sub behind the same `publish`/`subscribe` interface.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

ADMIN_QUEUE_CHANNEL = "admin:queue"


def ticket_channel(ticket_id: Any) -> str:
    return f"ticket:{ticket_id}"


def author_channel(author_id: str) -> str:
    return f"author:{author_id}"


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(channel, ())):
            # Drop-on-full: a slow consumer should never block the request that produced the event.
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self, channels: list[str], *, maxsize: int = 100) -> AsyncIterator[asyncio.Queue]:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        for ch in channels:
            self._subscribers[ch].add(q)
        try:
            yield q
        finally:
            for ch in channels:
                self._subscribers[ch].discard(q)
                if not self._subscribers[ch]:
                    self._subscribers.pop(ch, None)

    def subscriber_count(self) -> int:
        return sum(len(s) for s in self._subscribers.values())


broker = EventBroker()
