"""Server-Sent Events stream built on the broker. Emits a heartbeat so proxies keep the socket open."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from starlette.requests import Request

from app.realtime.broker import broker

HEARTBEAT_SECONDS = 15


async def event_stream(request: Request, channels: list[str]) -> AsyncIterator[dict]:
    async with broker.subscribe(channels) as q:
        yield {"event": "ready", "data": json.dumps({"channels": channels})}
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}
