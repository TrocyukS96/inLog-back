import uuid

import pytest
from httpx import AsyncClient

from app.services.notification import create_notification, serialize_notification
from app.services.notification_ws import NotificationConnectionManager
from tests.test_auth import login_user, register_user, verify_user_email


async def setup_project_with_users(client: AsyncClient) -> dict:
    owner_email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    invitee_email = f"invitee-{uuid.uuid4().hex[:8]}@example.com"

    await register_user(client, owner_email)
    await verify_user_email(client, owner_email)
    await register_user(client, invitee_email)
    await verify_user_email(client, invitee_email)

    owner_login = await login_user(client, owner_email)
    owner_headers = {"Authorization": f"Bearer {owner_login['access_token']}"}

    invitee_login = await login_user(client, invitee_email)
    invitee_headers = {"Authorization": f"Bearer {invitee_login['access_token']}"}
    invitee_id = invitee_login["user"]["id"]

    org_response = await client.post(
        "/api/organizations/organization/",
        json={
            "full_name": "Notifications Org LLC",
            "short_name": "NotifOrg",
            "address": "Moscow",
        },
        headers=owner_headers,
    )
    assert org_response.status_code == 201
    org_id = org_response.json()["id"]

    project_response = await client.post(
        "/api/projects/project/",
        json={
            "name": "Notification Project",
            "organization": org_id,
            "reservoir": "Sandstone",
        },
        headers=owner_headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    return {
        "owner_headers": owner_headers,
        "invitee_headers": invitee_headers,
        "invitee_id": invitee_id,
        "project_id": project_id,
        "invitee_email": invitee_email,
        "owner_email": owner_email,
    }


@pytest.mark.asyncio
async def test_project_invitation_flow(client: AsyncClient) -> None:
    context = await setup_project_with_users(client)

    invite_response = await client.post(
        f"/api/projects/{context['project_id']}/user-invitation/",
        json={"user": context["invitee_id"], "role": "member"},
        headers=context["owner_headers"],
    )
    assert invite_response.status_code == 201
    invitation_id = invite_response.json()["id"]

    list_response = await client.get(
        f"/api/projects/{context['project_id']}/user-invitation/",
        headers=context["owner_headers"],
    )
    assert list_response.status_code == 200
    invited_users = list_response.json()
    assert len(invited_users) == 1
    assert invited_users[0]["email"] == context["invitee_email"]

    invitee_notifications = await client.get(
        "/api/notifications/notification/",
        headers=context["invitee_headers"],
    )
    assert invitee_notifications.status_code == 200
    notifications = invitee_notifications.json()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "project_user_invitation"
    assert notifications[0]["data"]["project_user_invitation"]["id"] == invitation_id

    accept_response = await client.post(
        f"/api/projects/{context['project_id']}/user-invitation/response/",
        json={
            "action": "accept",
            "project_user_invitation": invitation_id,
        },
        headers=context["invitee_headers"],
    )
    assert accept_response.status_code == 204

    members_response = await client.get(
        f"/api/projects/{context['project_id']}/members/",
        headers=context["owner_headers"],
    )
    assert members_response.status_code == 200
    member_emails = [member["user"]["email"] for member in members_response.json()]
    assert context["invitee_email"] in member_emails

    owner_notifications = await client.get(
        "/api/notifications/notification/",
        headers=context["owner_headers"],
    )
    assert owner_notifications.status_code == 200
    owner_items = owner_notifications.json()
    assert any(item["type"] == "project_user_invitation_response" for item in owner_items)
    response_item = next(
        item for item in owner_items if item["type"] == "project_user_invitation_response"
    )
    assert response_item["data"]["accepted"] is True


@pytest.mark.asyncio
async def test_project_invitation_reject(client: AsyncClient) -> None:
    context = await setup_project_with_users(client)

    invite_response = await client.post(
        f"/api/projects/{context['project_id']}/user-invitation/",
        json={"user": context["invitee_id"], "role": "editor"},
        headers=context["owner_headers"],
    )
    invitation_id = invite_response.json()["id"]

    reject_response = await client.post(
        f"/api/projects/{context['project_id']}/user-invitation/response/",
        json={
            "action": "reject",
            "project_user_invitation": invitation_id,
        },
        headers=context["invitee_headers"],
    )
    assert reject_response.status_code == 204

    owner_notifications = await client.get(
        "/api/notifications/notification/",
        headers=context["owner_headers"],
    )
    response_item = next(
        item
        for item in owner_notifications.json()
        if item["type"] == "project_user_invitation_response"
    )
    assert response_item["data"]["accepted"] is False


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


@pytest.mark.asyncio
async def test_notification_manager_delivers_payload() -> None:
    manager = NotificationConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(42, websocket)
    await manager.send_to_user(
        42,
        {
            "id": 1,
            "type": "project_user_invitation",
            "is_read": False,
            "data": {"project": {"id": 1, "name": "WS Project"}},
        },
    )

    assert len(websocket.messages) == 1
    assert websocket.messages[0]["type"] == "project_user_invitation"


@pytest.mark.asyncio
async def test_create_notification_pushes_to_connected_user(client: AsyncClient) -> None:
    email = f"ws-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, email)
    await verify_user_email(client, email)
    login_data = await login_user(client, email)
    user_id = login_data["user"]["id"]

    manager = NotificationConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(user_id, websocket)

    from app.services import notification as notification_module

    original_manager = notification_module.notification_manager
    notification_module.notification_manager = manager

    try:
        from app.db.session import async_session

        async with async_session() as session:
            created = await create_notification(
                session,
                receiver_id=user_id,
                sender_id=None,
                notification_type="project_user_invitation",
                data={"project": {"id": 1, "name": "WS Project"}},
            )
            await session.commit()

        assert len(websocket.messages) == 1
        payload = websocket.messages[0]
        assert payload["id"] == created.id
        assert payload["data"]["project"]["name"] == "WS Project"
        assert payload["type"] == "project_user_invitation"

        serialized = serialize_notification(created)
        assert serialized.model_dump(mode="json")["id"] == payload["id"]
    finally:
        notification_module.notification_manager = original_manager
        await manager.disconnect(user_id, websocket)
