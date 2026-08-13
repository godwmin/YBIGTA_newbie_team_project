import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from mcp_server.errors import DomainError, ErrorCode
from mcp_server.schemas.price import (
    PriceHistory,
    PriceHistoryPoint,
    PriceRecord,
    TopGainers,
)

SYMBOL_PATTERN = re.compile(r"^KRW-[A-Z0-9]{2,10}$")


class PriceRepositoryProtocol(Protocol):
    async def get_latest_price(self, symbol: str) -> dict[str, Any] | None: ...

    async def get_top_gainers(self, limit: int) -> list[dict[str, Any]]: ...

    async def get_price_history(
        self,
        symbol: str,
        cutoff: datetime,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class PriceService:
    """Validate tool input and convert database rows to safe response models."""

    def __init__(
        self,
        repository: PriceRepositoryProtocol,
        max_top_gainers_limit: int = 20,
        max_history_hours: int = 168,
        max_history_rows: int = 500,
    ) -> None:
        self._repository = repository
        self._max_top_gainers_limit = max_top_gainers_limit
        self._max_history_hours = max_history_hours
        self._max_history_rows = max_history_rows

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise DomainError(ErrorCode.INVALID_SYMBOL, "symbol은 문자열이어야 합니다.")

        normalized = symbol.strip().upper()
        if not SYMBOL_PATTERN.fullmatch(normalized):
            raise DomainError(
                ErrorCode.INVALID_SYMBOL,
                "symbol은 KRW-BTC와 같은 형식으로 입력해주세요.",
            )
        return normalized

    @staticmethod
    def _validate_bounded_int(
        value: int,
        name: str,
        maximum: int,
        error_code: ErrorCode,
    ) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
            or value > maximum
        ):
            raise DomainError(error_code, f"{name}은 1~{maximum} 정수여야 합니다.")
        return value

    @staticmethod
    def _change_rate_percent(change_rate: Any) -> Decimal:
        return (Decimal(str(change_rate)) * Decimal(100)).quantize(Decimal("0.01"))

    @classmethod
    def _to_price_record(cls, row: dict[str, Any]) -> PriceRecord:
        return PriceRecord(
            **row,
            change_rate_percent=cls._change_rate_percent(row["change_rate"]),
        )

    async def get_latest_price(self, symbol: str) -> PriceRecord:
        normalized = self._normalize_symbol(symbol)
        row = await self._repository.get_latest_price(normalized)
        if row is None:
            raise DomainError(
                ErrorCode.DATA_NOT_FOUND,
                f"{normalized}의 수집 데이터가 없습니다.",
            )
        return self._to_price_record(row)

    async def get_top_gainers(self, limit: int) -> TopGainers:
        validated_limit = self._validate_bounded_int(
            limit,
            "limit",
            self._max_top_gainers_limit,
            ErrorCode.INVALID_LIMIT,
        )
        rows = await self._repository.get_top_gainers(validated_limit)
        coins = [self._to_price_record(row) for row in rows]
        return TopGainers(
            requested_limit=validated_limit,
            returned_count=len(coins),
            coins=coins,
        )

    async def get_price_history(self, symbol: str, hours: int) -> PriceHistory:
        normalized = self._normalize_symbol(symbol)
        validated_hours = self._validate_bounded_int(
            hours,
            "hours",
            self._max_history_hours,
            ErrorCode.INVALID_HOURS,
        )
        # Collector가 MySQL DATETIME에 timezone 없는 현재 시각을 저장하므로
        # 동일한 시간 기준을 사용합니다. 배포 EC2는 UTC로 통일합니다.
        cutoff = datetime.now() - timedelta(hours=validated_hours)  # noqa: DTZ005
        rows = await self._repository.get_price_history(
            normalized,
            cutoff,
            self._max_history_rows,
        )
        if not rows:
            raise DomainError(
                ErrorCode.DATA_NOT_FOUND,
                f"{normalized}의 최근 {validated_hours}시간 데이터가 없습니다.",
            )

        prices = [PriceHistoryPoint.model_validate(row) for row in rows]
        return PriceHistory(
            symbol=normalized,
            hours=validated_hours,
            returned_count=len(prices),
            max_rows=self._max_history_rows,
            prices=prices,
        )
