from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.realtime import manager

router = APIRouter(tags=["Realtime"])


@router.websocket("/ws/events")
async def events_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
