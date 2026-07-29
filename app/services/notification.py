from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services.notification_ws import notification_manager


def _avatar_url(user: User | None) -> str:
    if user is None or not user.avatar:
        return ""
    avatar = user.avatar
    if isinstance(avatar, dict):
        for key in ("small", "medium", "large", "original"):
            value = avatar.get(key)
            if value:
                return str(value)
    return ""


def serialize_notification_user(user: User | None) -> dict | None:
    if user is None:
        return None

    name = user.name or ""
    surname = user.surname or ""

    return {
        "first_name": name,
        "last_name": surname,
        "name": name,
        "surname": surname,
        "email": user.email,
        "avatar": _avatar_url(user),
    }


def serialize_notification(notification: Notification) -> NotificationRead:
    sender = serialize_notification_user(notification.sender)
    receiver = serialize_notification_user(notification.receiver)

    return NotificationRead(
        id=notification.id,
        type=notification.type,
        is_read=notification.is_read,
        is_deleted=notification.is_deleted,
        deleted=notification.is_deleted,
        data=notification.data or {},
        created_at=notification.created_at,
        sender=sender,
        receiver=receiver,
    )


async def list_user_notifications(db: AsyncSession, user: User) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.receiver_id == user.id,
            Notification.is_deleted.is_(False),
        )
        .options(
            selectinload(Notification.sender),
            selectinload(Notification.receiver),
        )
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_notification(
    db: AsyncSession,
    user: User,
    notification_id: int,
) -> Notification | None:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.receiver_id == user.id,
            Notification.is_deleted.is_(False),
        )
        .options(
            selectinload(Notification.sender),
            selectinload(Notification.receiver),
        )
    )
    return result.scalar_one_or_none()


async def update_notification(
    db: AsyncSession,
    notification: Notification,
    data: NotificationUpdate,
) -> Notification:
    if data.is_read is not None:
        notification.is_read = data.is_read

    await db.flush()
    await db.refresh(notification)
    return notification


async def delete_notification(db: AsyncSession, notification: Notification) -> None:
    notification.is_deleted = True
    await db.flush()


async def load_notification(db: AsyncSession, notification_id: int) -> Notification:
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .options(
            selectinload(Notification.sender),
            selectinload(Notification.receiver),
        )
    )
    return result.scalar_one()


async def push_notification_to_user(notification: Notification) -> None:
    serialized = serialize_notification(notification)
    await notification_manager.send_to_user(
        notification.receiver_id,
        serialized.model_dump(mode="json"),
    )


async def create_notification(
    db: AsyncSession,
    *,
    receiver_id: int,
    sender_id: int | None,
    notification_type: str,
    data: dict,
    push: bool = True,
) -> Notification:
    notification = Notification(
        receiver_id=receiver_id,
        sender_id=sender_id,
        type=notification_type,
        data=data,
    )
    db.add(notification)
    await db.flush()

    loaded = await load_notification(db, notification.id)
    if push:
        await push_notification_to_user(loaded)
    return loaded
