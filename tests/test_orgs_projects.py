import uuid

import pytest
from httpx import AsyncClient

from tests.test_auth import login_user, register_user, verify_user_email

TEST_PASSWORD = "password123"


@pytest.mark.asyncio
async def test_organization_and_project_crud(client: AsyncClient) -> None:
    email = f"org-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, email)
    await verify_user_email(client, email)
    login_data = await login_user(client, email)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    org_response = await client.post(
        "/api/organizations/organization/",
        json={
            "full_name": "Test Organization LLC",
            "short_name": "TestOrg",
            "address": "Moscow, Russia",
        },
        headers=headers,
    )
    assert org_response.status_code == 201
    organization = org_response.json()
    assert organization["full_name"] == "Test Organization LLC"
    assert organization["short_name"] == "TestOrg"
    org_id = organization["id"]

    list_response = await client.get("/api/organizations/organization/", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    project_response = await client.post(
        "/api/projects/project/",
        json={
            "name": "North Field",
            "organization": org_id,
            "reservoir": "Sandstone",
        },
        headers=headers,
    )
    assert project_response.status_code == 201
    project = project_response.json()
    assert project["name"] == "North Field"
    assert project["reservoir"] == "Sandstone"
    project_id = project["id"]

    filtered_projects = await client.get(
        f"/api/projects/project/?organization={org_id}",
        headers=headers,
    )
    assert filtered_projects.status_code == 200
    assert len(filtered_projects.json()) == 1

    detail_response = await client.get(
        f"/api/projects/project/{project_id}/",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == project_id

    patch_response = await client.patch(
        f"/api/projects/project/{project_id}/",
        json={"country": "Russia"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["country"] == "Russia"

    members_response = await client.get(
        f"/api/projects/{project_id}/members/",
        headers=headers,
    )
    assert members_response.status_code == 200
    members = members_response.json()
    assert len(members) == 1
    assert members[0]["role"] == "admin"
    assert members[0]["user"]["email"] == email

    delete_project_response = await client.delete(
        f"/api/projects/project/{project_id}/",
        headers=headers,
    )
    assert delete_project_response.status_code == 204

    delete_org_response = await client.delete(
        f"/api/organizations/organization/{org_id}/",
        headers=headers,
    )
    assert delete_org_response.status_code == 204

    empty_orgs = await client.get("/api/organizations/organization/", headers=headers)
    assert empty_orgs.status_code == 200
    assert empty_orgs.json() == []


@pytest.mark.asyncio
async def test_organizations_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/organizations/organization/")
    assert response.status_code == 401
