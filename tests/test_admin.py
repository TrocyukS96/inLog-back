import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.roles import PlatformRole
from app.db.session import async_session
from app.models.user import User
from tests.test_auth import login_user, register_user, verify_user_email

TEST_PASSWORD = "password123"


async def set_user_platform_role(email: str, role: str) -> None:
    async with async_session() as session:
        await session.execute(
            update(User).where(User.email == email.lower()).values(role=role)
        )
        await session.commit()


async def create_verified_user(client: AsyncClient, role: str = PlatformRole.MEMBER) -> tuple[str, dict]:
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, email)
    await verify_user_email(client, email)
    await set_user_platform_role(email, role)
    login_data = await login_user(client, email)
    return email, login_data


@pytest.mark.asyncio
async def test_admin_access_forbidden_for_member(client: AsyncClient) -> None:
    _, login_data = await create_verified_user(client, PlatformRole.MEMBER)

    response = await client.get(
        "/api/admin/access/",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_access_allowed_for_super_admin(client: AsyncClient) -> None:
    _, login_data = await create_verified_user(client, PlatformRole.SUPER_ADMIN)

    response = await client.get(
        "/api/admin/access/",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_super_admin"] is True
    assert "view_all_users" in payload["permissions"]


@pytest.mark.asyncio
async def test_admin_can_list_and_delete_member(client: AsyncClient) -> None:
    admin_email, admin_login = await create_verified_user(client, PlatformRole.ADMIN)
    member_email, member_login = await create_verified_user(client, PlatformRole.MEMBER)

    list_response = await client.get(
        "/api/admin/user/",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert list_response.status_code == 200
    emails = {item["email"] for item in list_response.json()["results"]}
    assert admin_email in emails
    assert member_email in emails

    member_id = member_login["user"]["id"]
    delete_response = await client.delete(
        f"/api/admin/user/{member_id}/",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_admin_cannot_delete_super_admin(client: AsyncClient) -> None:
    _, admin_login = await create_verified_user(client, PlatformRole.ADMIN)
    _, super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)

    delete_response = await client.delete(
        f"/api/admin/user/{super_login['user']['id']}/",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert delete_response.status_code == 400


@pytest.mark.asyncio
async def test_super_admin_can_update_user_role(client: AsyncClient) -> None:
    _, super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)
    member_email, member_login = await create_verified_user(client, PlatformRole.MEMBER)

    response = await client.patch(
        f"/api/admin/user/{member_login['user']['id']}/role/",
        headers={"Authorization": f"Bearer {super_login['access_token']}"},
        json={"role": PlatformRole.ADMIN},
    )
    assert response.status_code == 200
    assert response.json()["role"] == PlatformRole.ADMIN

    me_response = await client.post(
        "/api/auth/login/",
        json={"email": member_email, "password": TEST_PASSWORD},
    )
    assert me_response.status_code == 200
    assert me_response.json()["user"]["role"] == PlatformRole.ADMIN


@pytest.mark.asyncio
async def test_super_admin_cannot_assign_super_admin_via_api(client: AsyncClient) -> None:
    _, super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)
    _, member_login = await create_verified_user(client, PlatformRole.MEMBER)

    response = await client.patch(
        f"/api/admin/user/{member_login['user']['id']}/role/",
        headers={"Authorization": f"Bearer {super_login['access_token']}"},
        json={"role": PlatformRole.SUPER_ADMIN},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_super_admin_cannot_change_super_admin_role_via_api(client: AsyncClient) -> None:
    _, super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)
    _, other_super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)

    response = await client.patch(
        f"/api/admin/user/{other_super_login['user']['id']}/role/",
        headers={"Authorization": f"Bearer {super_login['access_token']}"},
        json={"role": PlatformRole.ADMIN},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_tasks_include_creator_and_members(client: AsyncClient) -> None:
    _, super_login = await create_verified_user(client, PlatformRole.SUPER_ADMIN)
    member_email, member_login = await create_verified_user(client, PlatformRole.MEMBER)
    headers = {"Authorization": f"Bearer {super_login['access_token']}"}

    org_response = await client.post(
        "/api/organizations/organization/",
        headers=headers,
        json={"full_name": "Admin Org", "short_name": "AO"},
    )
    assert org_response.status_code == 201
    org_id = org_response.json()["id"]

    project_response = await client.post(
        "/api/projects/project/",
        headers=headers,
        json={"name": "Admin Project", "organization": org_id},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    member_headers = {"Authorization": f"Bearer {member_login['access_token']}"}
    invite_response = await client.post(
        f"/api/projects/{project_id}/user-invitation/",
        headers=headers,
        json={"user": member_login["user"]["id"], "role": "member"},
    )
    assert invite_response.status_code == 201
    invitation_id = invite_response.json()["id"]

    accept_response = await client.post(
        f"/api/projects/{project_id}/user-invitation/response/",
        headers=member_headers,
        json={"action": "accept", "project_user_invitation": invitation_id},
    )
    assert accept_response.status_code == 204

    task_response = await client.post(
        f"/api/projects/{project_id}/tasks/task/",
        headers=headers,
        json={"name": "Admin task", "project": project_id},
    )
    assert task_response.status_code == 201

    list_response = await client.get("/api/admin/task/", headers=headers)
    assert list_response.status_code == 200
    tasks = list_response.json()["results"]
    assert tasks
    task = next(item for item in tasks if item["name"] == "Admin task")
    assert task["creator"]["email"] == super_login["user"]["email"]
    assert task["creator_name"]
    assert len(task["members"]) >= 2
    member_emails = {member["email"] for member in task["members"]}
    assert super_login["user"]["email"] in member_emails
    assert member_email in member_emails


@pytest.mark.asyncio
async def test_admin_catalog_endpoints(client: AsyncClient) -> None:
    _, login_data = await create_verified_user(client, PlatformRole.SUPER_ADMIN)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    for path in (
        "/api/admin/member/",
        "/api/admin/organization/",
        "/api/admin/project/",
        "/api/admin/task/",
        "/api/admin/task-status/",
        "/api/admin/task-tag/",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200
        assert "results" in response.json()
