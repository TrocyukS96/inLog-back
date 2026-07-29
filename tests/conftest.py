from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def disable_outbound_email() -> None:
    """Tests register users with @example.com — never send real SMTP from pytest."""
    from app.services import email as email_module

    original_send_email = email_module.send_email
    email_module.send_email = AsyncMock(return_value=None)
    yield
    email_module.send_email = original_send_email


@pytest.fixture(scope="session")
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
