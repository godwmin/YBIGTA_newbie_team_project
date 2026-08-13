from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from mcp_server.errors import DomainError, ErrorCode
from mcp_server.services.price_service import PriceService

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 8, 13, 6, 0, tzinfo=UTC)


class FakePriceRepository:
    def __init__(self) -> None:
        self.last_history_call: tuple[str, datetime, int] | None = None

    async def get_latest_price(self, symbol: str) -> dict[str, Any] | None:
        if symbol != "KRW-BTC":
            return None
        return {
            "symbol": symbol,
            "price": Decimal("150000000.0000"),
            "change_rate": Decimal("0.0325"),
            "collected_at": NOW,
        }

    async def get_top_gainers(self, limit: int) -> list[dict[str, Any]]:
        rows = [
            {
                "symbol": "KRW-SOL",
                "price": Decimal("280000.0000"),
                "change_rate": Decimal("0.041"),
                "collected_at": NOW,
            },
            {
                "symbol": "KRW-BTC",
                "price": Decimal("150000000.0000"),
                "change_rate": Decimal("0.0325"),
                "collected_at": NOW,
            },
        ]
        return rows[:limit]

    async def get_price_history(
        self,
        symbol: str,
        cutoff: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        self.last_history_call = (symbol, cutoff, limit)
        return [
            {
                "price": Decimal("150000000.0000"),
                "change_rate": Decimal("0.0325"),
                "collected_at": NOW,
            }
        ]


@pytest.fixture
def repository() -> FakePriceRepository:
    return FakePriceRepository()


@pytest.fixture
def service(repository: FakePriceRepository) -> PriceService:
    return PriceService(repository, max_history_rows=500)


async def test_symbol_is_normalized(service: PriceService) -> None:
    result = await service.get_latest_price(" krw-btc ")

    assert result.symbol == "KRW-BTC"
    assert result.change_rate_percent == Decimal("3.25")


async def test_sql_injection_like_symbol_is_rejected(service: PriceService) -> None:
    with pytest.raises(DomainError) as captured:
        await service.get_latest_price("KRW-BTC'; DROP TABLE coin_prices")

    assert captured.value.code == ErrorCode.INVALID_SYMBOL


@pytest.mark.parametrize("limit", [0, 21, True, 1.5])
async def test_top_gainers_limit_is_restricted(
    service: PriceService, limit: Any
) -> None:
    with pytest.raises(DomainError) as captured:
        await service.get_top_gainers(limit)

    assert captured.value.code == ErrorCode.INVALID_LIMIT


async def test_top_gainers_returns_requested_count(service: PriceService) -> None:
    result = await service.get_top_gainers(1)

    assert result.returned_count == 1
    assert result.coins[0].symbol == "KRW-SOL"


@pytest.mark.parametrize("hours", [0, 169, True, "24"])
async def test_history_hours_is_restricted(service: PriceService, hours: Any) -> None:
    with pytest.raises(DomainError) as captured:
        await service.get_price_history("KRW-BTC", hours)

    assert captured.value.code == ErrorCode.INVALID_HOURS


async def test_history_has_internal_row_limit(
    service: PriceService,
    repository: FakePriceRepository,
) -> None:
    result = await service.get_price_history("KRW-BTC", 24)

    assert result.max_rows == 500
    assert repository.last_history_call is not None
    assert repository.last_history_call[2] == 500
