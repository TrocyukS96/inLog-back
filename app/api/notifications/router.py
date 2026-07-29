from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services.notification import (
    delete_notification,
    get_user_notification,
    list_user_notifications,
    serialize_notification,
    update_notification,
)

router = APIRouter(prefix="/notifications/notification", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationRead]:
    notifications = await list_user_notifications(db, current_user)
    return [serialize_notification(item) for item in notifications]


@router.patch("/{notification_id}/", response_model=NotificationRead)
async def patch_notification(
    notification_id: int,
    data: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    notification = await get_user_notification(db, current_user, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    updated = await update_notification(db, notification, data)
    return serialize_notification(updated)


@router.delete("/{notification_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    notification = await get_user_notification(db, current_user, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    await delete_notification(db, notification)
