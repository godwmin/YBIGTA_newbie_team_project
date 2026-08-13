from dataclasses import dataclass

from mcp_server.services.price_service import PriceService


@dataclass(frozen=True)
class AppContext:
    price_service: PriceService
