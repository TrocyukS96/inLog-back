import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session
from app.models.notification import Notification
from app.models.user import User
from tests.test_auth import login_user, register_user, verify_user_email

TEST_PASSWORD = "password123"


async def create_notification(
    receiver_id: int,
    *,
    sender_id: int | None = None,
    notification_type: str = "project_user_invitation",
    is_read: bool = False,
    data: dict | None = None,
) -> Notification:
    async with async_session() as session:
        notification = Notification(
            receiver_id=receiver_id,
            sender_id=sender_id,
            type=notification_type,
            is_read=is_read,
            data=data or {"project": {"id": 1, "name": "Test Project"}},
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification


@pytest.mark.asyncio
async def test_notifications_list_patch_delete(client: AsyncClient) -> None:
    receiver_email = f"recv-{uuid.uuid4().hex[:8]}@example.com"
    sender_email = f"send-{uuid.uuid4().hex[:8]}@example.com"

    await register_user(client, receiver_email)
    await verify_user_email(client, receiver_email)
    await register_user(client, sender_email)
    await verify_user_email(client, sender_email)

    login_data = await login_user(client, receiver_email)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    async with async_session() as session:
        receiver = (
            await session.execute(select(User).where(User.email == receiver_email.lower()))
        ).scalar_one()
        sender = (
            await session.execute(select(User).where(User.email == sender_email.lower()))
        ).scalar_one()
        receiver_id = receiver.id
        sender_id = sender.id

    notification = await create_notification(receiver_id, sender_id=sender_id)

    list_response = await client.get("/api/notifications/notification/", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == notification.id
    assert items[0]["type"] == "project_user_invitation"
    assert items[0]["is_read"] is False
    assert items[0]["sender"]["email"] == sender_email.lower()
    assert items[0]["receiver"]["email"] == receiver_email.lower()

    patch_response = await client.patch(
        f"/api/notifications/notification/{notification.id}/",
        json={"is_read": True},
        headers=headers,
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["is_read"] is True
    assert patched["id"] == notification.id

    delete_response = await client.delete(
        f"/api/notifications/notification/{notification.id}/",
        headers=headers,
    )
    assert delete_response.status_code == 204

    list_after_delete = await client.get("/api/notifications/notification/", headers=headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_notifications_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/notifications/notification/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_notifications_not_found(client: AsyncClient) -> None:
    email = f"notif-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, email)
    await verify_user_email(client, email)
    login_data = await login_user(client, email)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    patch_response = await client.patch(
        "/api/notifications/notification/999999/",
        json={"is_read": True},
        headers=headers,
    )
    assert patch_response.status_code == 404
