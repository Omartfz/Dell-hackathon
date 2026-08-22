"""SafeContext — FastAPI entrypoint.

Serves the console, the JSON API, and a WebSocket that pushes every stream event to
connected browsers. No build step: the UI is plain HTML/CSS/JS served from disk, so
the box needs Python and nothing else.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import RUNNER, router
from app.db.client import adb, close, replica_set_ready
from app.db.indexes import ensure
from config import settings

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class Hub:
    """Fan-out to connected browsers. A slow client is dropped, never blocking."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def join(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            targets = list(self._clients)
        if not targets:
            return
        payload = json.dumps(message, default=str)
        dead = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


hub = Hub()


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    RUNNER._broadcast = hub.broadcast
    try:
        await ensure(adb())
    except Exception as exc:  # a fresh box may not have mongod up yet
        print(f"[safecontext] index setup deferred: {exc}")
    ready, detail = await replica_set_ready()
    print(f"[safecontext] mongo: {detail}")
    if ready:
        await RUNNER.start()
        print("[safecontext] change stream started")
    else:
        print("[safecontext] stream NOT started — see /api/health")
    yield
    await RUNNER.stop()
    await close()


app = FastAPI(title="SafeContext", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.join(ws)
    try:
        await ws.send_text(json.dumps({"type": "status", **(await RUNNER.state())},
                                      default=str))
        while True:
            await ws.receive_text()          # client keepalive; we only push
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(ws)


@app.get("/")
async def index():
    return FileResponse(os.path.join(WEB, "index.html"))


app.mount("/static", StaticFiles(directory=WEB), name="static")


def main() -> None:
    import uvicorn

    s = settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    main()
