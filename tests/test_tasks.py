import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session
from app.models.task import Task, TaskStatus
from app.services.task import generate_task_slug, get_default_status
from tests.test_auth import login_user, register_user, verify_user_email

TEST_PASSWORD = "password123"


async def setup_project(client: AsyncClient) -> tuple[dict, int, str]:
    email = f"tasks-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, email)
    await verify_user_email(client, email)
    login_data = await login_user(client, email)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    org_response = await client.post(
        "/api/organizations/organization/",
        json={"full_name": "Tasks Org", "short_name": "TasksOrg", "address": "Moscow"},
        headers=headers,
    )
    org_id = org_response.json()["id"]

    project_response = await client.post(
        "/api/projects/project/",
        json={"name": "Tasks Project", "organization": org_id, "reservoir": "Sandstone"},
        headers=headers,
    )
    project_id = project_response.json()["id"]

    return headers, project_id, email


async def create_sample_task(project_id: int, creator_id: int, name: str = "Sample task") -> Task:
    async with async_session() as session:
        default_status = await get_default_status(session, project_id)
        task = Task(
            project_id=project_id,
            creator_id=creator_id,
            status_id=default_status.id,
            name=name,
            slug=generate_task_slug(name),
            priority="medium",
            is_template=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


@pytest.mark.asyncio
async def test_task_statuses_endpoint(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)

    response = await client.get(f"/api/projects/{project_id}/tasks/status/", headers=headers)
    assert response.status_code == 200

    statuses = response.json()
    assert len(statuses) == 3
    assert statuses[0]["name_en"] == "No status"
    assert statuses[2]["name_en"] == "Closed"
    assert all(status["project"] == project_id for status in statuses)


@pytest.mark.asyncio
async def test_task_tags_endpoint(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)

    response = await client.get(
        f"/api/projects/{project_id}/tasks/tag/",
        params={"limit": 9999, "is_orphan": False},
        headers=headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 0
    assert payload["results"] == []
    assert payload["next"] is None
    assert payload["previous"] is None


@pytest.mark.asyncio
async def test_tasks_list_endpoint(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)
    login_data = await login_user(client, email)

    await create_sample_task(project_id, login_data["user"]["id"], "First task")
    await create_sample_task(project_id, login_data["user"]["id"], "Second task")

    response = await client.get(
        f"/api/projects/{project_id}/tasks/task/",
        params={"limit": 100, "offset": 0, "is_template": False},
        headers=headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["results"]) == 2
    assert payload["results"][0]["name"] in {"First task", "Second task"}
    assert payload["results"][0]["status"]["name_en"] == "No status"
    assert payload["results"][0]["creator"]["email"]


@pytest.mark.asyncio
async def test_tasks_filter_by_status(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)
    login_data = await login_user(client, email)

    await client.get(f"/api/projects/{project_id}/tasks/status/", headers=headers)

    async with async_session() as session:
        statuses = (
            await session.execute(
                select(TaskStatus).where(TaskStatus.project_id == project_id)
            )
        ).scalars().all()
        closed_status = next(status for status in statuses if status.name_en == "Closed")

    task = await create_sample_task(project_id, login_data["user"]["id"], "Closed task")
    async with async_session() as session:
        db_task = (
            await session.execute(select(Task).where(Task.id == task.id))
        ).scalar_one()
        db_task.status_id = closed_status.id
        await session.commit()

    response = await client.get(
        f"/api/projects/{project_id}/tasks/task/",
        params={"status": closed_status.id, "limit": 100, "is_template": False},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["status"]["name_en"] == "Closed"


@pytest.mark.asyncio
async def test_tasks_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/projects/1/tasks/status/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_task_crud_via_api(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)

    create_response = await client.post(
        f"/api/projects/{project_id}/tasks/task/",
        json={"name": "New task", "priority": "important", "is_template": False},
        headers=headers,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "New task"
    assert created["priority"] == "important"
    assert created["slug"]
    assert created["status"]["name_en"] == "No status"
    task_slug = created["slug"]

    detail_response = await client.get(
        f"/api/projects/{project_id}/tasks/task/{task_slug}/",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == created["id"]

    statuses_response = await client.get(
        f"/api/projects/{project_id}/tasks/status/",
        headers=headers,
    )
    closed_status_id = next(
        status["id"]
        for status in statuses_response.json()
        if status["name_en"] == "Closed"
    )

    patch_response = await client.patch(
        f"/api/projects/{project_id}/tasks/task/{task_slug}/",
        json={
            "id": created["id"],
            "name": "Updated task",
            "description": "Task description",
            "status": closed_status_id,
            "status_position": 2,
        },
        headers=headers,
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Updated task"
    assert patched["description"] == "Task description"
    assert patched["status"]["name_en"] == "Closed"
    assert patched["status_position"] == 2

    delete_response = await client.delete(
        f"/api/projects/{project_id}/tasks/task/{task_slug}/",
        headers=headers,
    )
    assert delete_response.status_code == 204

    list_response = await client.get(
        f"/api/projects/{project_id}/tasks/task/",
        params={"limit": 100, "is_template": False},
        headers=headers,
    )
    assert list_response.json()["count"] == 0


@pytest.mark.asyncio
async def test_create_subtask(client: AsyncClient) -> None:
    headers, project_id, email = await setup_project(client)

    parent_response = await client.post(
        f"/api/projects/{project_id}/tasks/task/",
        json={"name": "Parent task", "is_template": False},
        headers=headers,
    )
    parent = parent_response.json()

    subtask_response = await client.post(
        f"/api/projects/{project_id}/tasks/task/",
        json={"name": "Sub task", "parent": parent["id"], "is_template": False},
        headers=headers,
    )
    assert subtask_response.status_code == 201
    subtask = subtask_response.json()
    assert subtask["parent"] == parent["id"]

    detail_response = await client.get(
        f"/api/projects/{project_id}/tasks/task/{parent['slug']}/",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert len(detail_response.json()["subtasks"]) == 1
    assert detail_response.json()["subtasks"][0]["name"] == "Sub task"

