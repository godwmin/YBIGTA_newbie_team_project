import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from mcp_server.config import Settings

ConnectionFactory = Callable[[], Connection]


class PriceRepository:
    """Execute fixed, parameterized SELECT queries against coin_prices."""

    def __init__(
        self,
        settings: Settings,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._settings = settings
        self._connection_factory = connection_factory or self._connect

    def _connect(self) -> Connection:
        return pymysql.connect(
            host=self._settings.db_host,
            port=self._settings.db_port,
            user=self._settings.db_user,
            password=self._settings.db_password,
            database=self._settings.db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=self._settings.db_connect_timeout,
            read_timeout=self._settings.db_connect_timeout,
            write_timeout=self._settings.db_connect_timeout,
            autocommit=True,
        )

    def _fetch_all_sync(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())
        finally:
            connection.close()

    async def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_all_sync, query, params)

    async def get_latest_price(self, symbol: str) -> dict[str, Any] | None:
        rows = await self._fetch_all(
            """
            SELECT symbol, price, change_rate, collected_at
            FROM coin_prices
            WHERE symbol = %s
            ORDER BY collected_at DESC, id DESC
            LIMIT 1
            """,
            (symbol,),
        )
        return rows[0] if rows else None

    async def get_top_gainers(self, limit: int) -> list[dict[str, Any]]:
        return await self._fetch_all(
            """
            WITH latest_prices AS (
                SELECT
                    symbol,
                    price,
                    change_rate,
                    collected_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol
                        ORDER BY collected_at DESC, id DESC
                    ) AS row_number
                FROM coin_prices
            )
            SELECT symbol, price, change_rate, collected_at
            FROM latest_prices
            WHERE row_number = 1
            ORDER BY change_rate DESC, symbol ASC
            LIMIT %s
            """,
            (limit,),
        )

    async def get_price_history(
        self,
        symbol: str,
        cutoff: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await self._fetch_all(
            """
            SELECT price, change_rate, collected_at
            FROM coin_prices
            WHERE symbol = %s
              AND collected_at >= %s
            ORDER BY collected_at DESC, id DESC
            LIMIT %s
            """,
            (symbol, cutoff, limit),
        )
