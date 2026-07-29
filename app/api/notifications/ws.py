from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select

from app.core.security import decode_token
from app.db.session import async_session
from app.models.user import User
from app.services.notification_ws import notification_manager

ws_router = APIRouter(tags=["notifications"])


async def _authenticate_ws_token(token: str) -> User | None:
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return user


@ws_router.websocket("/notifications/")
async def notifications_websocket(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    user = await _authenticate_ws_token(token)
    if user is None:
        await websocket.close(code=4401)
        return

    await notification_manager.connect(user.id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await notification_manager.disconnect(user.id, websocket)
