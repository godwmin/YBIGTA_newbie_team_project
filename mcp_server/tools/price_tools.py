import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from mcp_server.dependencies import AppContext
from mcp_server.errors import DomainError, ErrorCode

logger = logging.getLogger(__name__)


async def _safe_call(operation: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    try:
        result = await operation()
        return {"ok": True, "data": result.model_dump(mode="json")}
    except DomainError as error:
        return {
            "ok": False,
            "error": {"code": error.code.value, "message": error.message},
        }
    except Exception:
        logger.exception("MCP tool execution failed")
        return {
            "ok": False,
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "데이터 조회 중 서버 오류가 발생했습니다.",
            },
        }


def register_price_tools(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool()
    async def get_latest_price(
        symbol: Annotated[
            str,
            Field(
                min_length=6,
                max_length=20,
                pattern=r"^[Kk][Rr][Ww]-[A-Za-z0-9]{2,10}$",
                description="업비트 마켓 심볼. 예: KRW-BTC",
            ),
        ],
        ctx: Context[AppContext],
    ) -> dict[str, Any]:
        """특정 코인의 가장 최근 수집 시세를 조회합니다."""
        service = ctx.request_context.lifespan_context.price_service
        return await _safe_call(lambda: service.get_latest_price(symbol))

    @mcp.tool()
    async def get_top_gainers(
        limit: Annotated[
            int,
            Field(ge=1, le=20, description="반환할 코인 수. 1~20"),
        ],
        ctx: Context[AppContext],
    ) -> dict[str, Any]:
        """각 코인의 최신 값을 기준으로 상승률 상위 N개를 조회합니다."""
        service = ctx.request_context.lifespan_context.price_service
        return await _safe_call(lambda: service.get_top_gainers(limit))

    @mcp.tool()
    async def get_price_history(
        symbol: Annotated[
            str,
            Field(
                min_length=6,
                max_length=20,
                pattern=r"^[Kk][Rr][Ww]-[A-Za-z0-9]{2,10}$",
                description="업비트 마켓 심볼. 예: KRW-BTC",
            ),
        ],
        hours: Annotated[
            int,
            Field(ge=1, le=168, description="조회할 과거 시간. 1~168"),
        ],
        ctx: Context[AppContext],
    ) -> dict[str, Any]:
        """특정 코인의 지난 N시간 시세를 최신순으로 조회합니다."""
        service = ctx.request_context.lifespan_context.price_service
        return await _safe_call(lambda: service.get_price_history(symbol, hours))
