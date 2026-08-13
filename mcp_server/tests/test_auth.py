import pytest

from mcp_server.auth import StaticBearerTokenVerifier

pytestmark = pytest.mark.asyncio


async def test_valid_bearer_token_is_accepted() -> None:
    verifier = StaticBearerTokenVerifier("a" * 32, "http://localhost:8000/mcp")

    access_token = await verifier.verify_token("a" * 32)

    assert access_token is not None
    assert access_token.client_id == "nextjs-agent"
    assert access_token.scopes == ["mcp:read"]


async def test_invalid_bearer_token_is_rejected() -> None:
    verifier = StaticBearerTokenVerifier("a" * 32, "http://localhost:8000/mcp")

    assert await verifier.verify_token("b" * 32) is None
