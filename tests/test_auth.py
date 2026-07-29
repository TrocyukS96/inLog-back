import uuid

import pytest
from httpx import AsyncClient

from tests.helpers import get_verification_credentials

TEST_PASSWORD = "password123"


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

    uid, key = await get_verification_credentials(unique_email)
    verify_email_response = await client.post(
        "/api/auth/registration/verify-email/",
        json={"uid": uid, "key": key},
    )
    assert verify_email_response.status_code == 200
    assert verify_email_response.json()["detail"] == "Email verified successfully."

    login_response = await client.post(
        "/api/auth/login/",
        json={"email": unique_email, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["user"]["email"] == unique_email

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
