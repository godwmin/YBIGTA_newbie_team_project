from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PriceRecord(BaseModel):
    symbol: str
    price: Decimal
    change_rate: Decimal
    change_rate_percent: Decimal
    collected_at: datetime


class PriceHistoryPoint(BaseModel):
    price: Decimal
    change_rate: Decimal
    collected_at: datetime


class PriceHistory(BaseModel):
    symbol: str
    hours: int
    returned_count: int
    max_rows: int
    prices: list[PriceHistoryPoint]


class TopGainers(BaseModel):
    requested_limit: int
    returned_count: int
    coins: list[PriceRecord]
