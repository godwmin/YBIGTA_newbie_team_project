from datetime import UTC, datetime
from typing import Any

import pytest
from typing_extensions import Self

from mcp_server.config import Settings
from mcp_server.repositories.price_repository import PriceRepository

pytestmark = pytest.mark.asyncio


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""
        self.params: tuple[Any, ...] = ()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True


def make_settings() -> Settings:
    return Settings(
        db_host="localhost",
        db_port=3306,
        db_name="crypto_db",
        db_user="mcp_user",
        db_password="test-password",
        db_connect_timeout=5,
        mcp_auth_token="a" * 32,
        mcp_server_url="http://localhost:8000/mcp",
        mcp_host="127.0.0.1",
        mcp_port=8000,
        max_top_gainers_limit=20,
        max_history_hours=168,
        max_history_rows=500,
    )


async def test_symbol_is_bound_as_a_query_parameter() -> None:
    malicious_symbol = "KRW-BTC'; DROP TABLE coin_prices"
    cursor = FakeCursor([])
    connection = FakeConnection(cursor)
    repository = PriceRepository(
        make_settings(),
        connection_factory=lambda: connection,  # type: ignore[arg-type]
    )

    await repository.get_latest_price(malicious_symbol)

    assert malicious_symbol not in cursor.query
    assert cursor.params == (malicious_symbol,)
    assert connection.closed is True


async def test_history_has_a_bound_sql_limit() -> None:
    cursor = FakeCursor([])
    connection = FakeConnection(cursor)
    repository = PriceRepository(
        make_settings(),
        connection_factory=lambda: connection,  # type: ignore[arg-type]
    )
    cutoff = datetime(2026, 8, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)

    await repository.get_price_history("KRW-BTC", cutoff, 500)

    assert cursor.params == ("KRW-BTC", cutoff, 500)
    assert "LIMIT %s" in cursor.query
