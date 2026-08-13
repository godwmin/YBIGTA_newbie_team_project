from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.auth import StaticBearerTokenVerifier
from mcp_server.config import get_settings
from mcp_server.dependencies import AppContext
from mcp_server.repositories.price_repository import PriceRepository
from mcp_server.services.price_service import PriceService
from mcp_server.tools.price_tools import register_price_tools

settings = get_settings()


@asynccontextmanager
async def app_lifespan(_: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
    repository = PriceRepository(settings)
    yield AppContext(
        price_service=PriceService(
            repository=repository,
            max_top_gainers_limit=settings.max_top_gainers_limit,
            max_history_hours=settings.max_history_hours,
            max_history_rows=settings.max_history_rows,
        )
    )


mcp = MCPServer(
    name="ybigta-crypto-price-mcp",
    instructions="수집된 업비트 코인 시세를 read-only Tool로 조회합니다.",
    lifespan=app_lifespan,
    token_verifier=StaticBearerTokenVerifier(
        expected_token=settings.mcp_auth_token,
        resource=settings.mcp_server_url,
    ),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.mcp_server_url),
        resource_server_url=AnyHttpUrl(settings.mcp_server_url),
        required_scopes=["mcp:read"],
    ),
)

register_price_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    """Unauthenticated health endpoint for Nginx and deployment checks."""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        stateless_http=True,
        json_response=True,
    )
