import asyncio
from collections.abc import Iterable

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        async with self._lock:
            connections: Iterable[WebSocket] = tuple(self._connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)

        if stale:
            async with self._lock:
                for connection in stale:
                    if connection in self._connections:
                        self._connections.remove(connection)


manager = ConnectionManager()
