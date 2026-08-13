import pytest
from mcp.server import MCPServer

from mcp_server.dependencies import AppContext
from mcp_server.tools.price_tools import register_price_tools

pytestmark = pytest.mark.asyncio


async def test_exactly_three_required_tools_are_registered() -> None:
    server: MCPServer[AppContext] = MCPServer("test-server")
    register_price_tools(server)

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == [
        "get_latest_price",
        "get_top_gainers",
        "get_price_history",
    ]
    assert tools[1].input_schema["properties"]["limit"]["maximum"] == 20
    assert tools[2].input_schema["properties"]["hours"]["maximum"] == 168
