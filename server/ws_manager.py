"""
WebSocket Manager — handles connections to performer view and editor clients.

Broadcasts state snapshots from ShowController to all connected clients.
Receives commands (pause, skip, go_back, etc.) from clients and routes
them to ShowController.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._server_loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        if self._server_loop is None:
            self._server_loop = asyncio.get_running_loop()
        async with self._lock:
            self._connections.append(ws)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info("WebSocket client disconnected (%d total)", len(self._connections))

    async def broadcast(self, data: dict):
        """Send a state update to all connected clients."""
        if not self._connections:
            return
        payload = json.dumps({"type": "state_update", "data": data})
        async with self._lock:
            stale = []
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._connections.remove(ws)

    def broadcast_sync(self, data: dict):
        """Thread-safe broadcast — always dispatches to the uvicorn event loop
        regardless of which thread the caller is on."""
        if self._server_loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self._server_loop)
        except RuntimeError:
            pass

    @property
    def client_count(self) -> int:
        return len(self._connections)
