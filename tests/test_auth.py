import uuid

import pytest
from httpx import AsyncClient

from tests.helpers import (
    get_email_change_credentials,
    get_password_reset_credentials,
    get_verification_credentials,
)

TEST_PASSWORD = "password123"
NEW_PASSWORD = "newpassword123"


async def register_user(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/auth/registration/",
        json={
            "email": email,
            "password1": TEST_PASSWORD,
            "password2": TEST_PASSWORD,
            "receive_advertisement": False,
            "receive_notifications": False,
            "belonging": "common",
        },
    )
    assert response.status_code == 201


async def verify_user_email(client: AsyncClient, email: str) -> None:
    uid, key = await get_verification_credentials(email)
    response = await client.post(
        "/api/auth/registration/verify-email/",
        json={"uid": uid, "key": key},
    )
    assert response.status_code == 200


async def login_user(client: AsyncClient, email: str, password: str = TEST_PASSWORD) -> dict:
    response = await client.post(
        "/api/auth/login/",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient) -> None:
    unique_email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, unique_email)

    login_before_verify = await client.post(
        "/api/auth/login/",
        json={"email": unique_email, "password": TEST_PASSWORD},
    )
    assert login_before_verify.status_code == 403
    assert login_before_verify.json()["detail"] == "Please verify your email before logging in."

    await verify_user_email(client, unique_email)
    login_data = await login_user(client, unique_email)

    verify_response = await client.post(
        "/api/auth/token/verify/",
        json={"token": login_data["access_token"]},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["token"] == login_data["access_token"]

    me_response = await client.get(
        "/api/users/me/",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == unique_email


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient) -> None:
    unique_email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, unique_email)
    await verify_user_email(client, unique_email)

    reset_response = await client.post(
        "/api/auth/password/reset/",
        json={"email": unique_email},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["email"] == unique_email

    uid, token = await get_password_reset_credentials(unique_email)
    confirm_response = await client.post(
        "/api/auth/password/reset/confirm/",
        json={
            "uid": uid,
            "token": token,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["detail"] == "Password has been reset successfully."

    old_login = await client.post(
        "/api/auth/login/",
        json={"email": unique_email, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    login_data = await login_user(client, unique_email, NEW_PASSWORD)
    assert login_data["user"]["email"] == unique_email


@pytest.mark.asyncio
async def test_confirm_email_change_flow(client: AsyncClient) -> None:
    unique_email = f"change-{uuid.uuid4().hex[:8]}@example.com"
    new_email = f"new-{uuid.uuid4().hex[:8]}@example.com"

    await register_user(client, unique_email)
    await verify_user_email(client, unique_email)
    login_data = await login_user(client, unique_email)
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    update_response = await client.patch(
        "/api/users/me/",
        data={"email": new_email},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["email"] == unique_email

    uid, token, pending_email = await get_email_change_credentials(login_data["user"]["id"])
    confirm_response = await client.post(
        "/api/users/me/confirm-email-change/",
        json={"email": pending_email, "uid": uid, "token": token},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["detail"] == "Email changed successfully."

    me_response = await client.get("/api/users/me/", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == new_email


@pytest.mark.asyncio
async def test_resend_verification_email(client: AsyncClient) -> None:
    unique_email = f"resend-{uuid.uuid4().hex[:8]}@example.com"
    await register_user(client, unique_email)

    response = await client.post(
        "/api/auth/registration/resend-email/",
        json={"email": unique_email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == unique_email
    assert data["detail"] == "Verification email has been sent."


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    unique_email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password1": TEST_PASSWORD,
        "password2": TEST_PASSWORD,
        "receive_advertisement": False,
    }

    first = await client.post("/api/auth/registration/", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/registration/", json=payload)
    assert second.status_code == 400
    assert "email" in second.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login/",
        json={"email": "missing@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
