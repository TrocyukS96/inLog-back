import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(user_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections.get(user_id, set()))

        stale: list[tuple[int, WebSocket]] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.exception("Failed to send notification websocket message")
                stale.append((user_id, websocket))

        for uid, websocket in stale:
            await self.disconnect(uid, websocket)


notification_manager = NotificationConnectionManager()
