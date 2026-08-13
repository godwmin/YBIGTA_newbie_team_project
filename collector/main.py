"""Collect current Upbit prices and append them to MySQL."""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pymysql
import requests
from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
SYMBOLS = ("KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"필수 환경변수가 비어 있습니다: {name}")
    return value


def fetch_upbit_data(
    *,
    symbols: tuple[str, ...] = SYMBOLS,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Fetch and validate the current ticker payload from Upbit."""
    response = requests.get(
        UPBIT_TICKER_URL,
        params={"markets": ",".join(symbols)},
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise TypeError("Upbit 응답이 배열 형식이 아닙니다.")

    expected = set(symbols)
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict) or not {
            "market",
            "trade_price",
            "signed_change_rate",
        }.issubset(item):
            raise ValueError("Upbit 응답에 필수 필드가 없습니다.")
        if item["market"] not in expected:
            continue
        rows.append(item)

    if not rows:
        raise ValueError("저장할 Upbit 시세가 없습니다.")
    return rows


def save_to_db(
    data_list: list[dict[str, Any]],
    *,
    collected_at: datetime | None = None,
) -> int:
    """Insert one collection batch and return the inserted row count."""
    if not data_list:
        return 0

    # MySQL DATETIME에는 timezone 정보가 없으므로 UTC 기준의 naive datetime으로 통일합니다.
    collected_at = collected_at or datetime.now(UTC).replace(tzinfo=None)
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("COLLECTOR_DB_USER", "collector_user"),
        password=required_env("COLLECTOR_DB_PASSWORD"),
        database=os.getenv("DB_NAME", "crypto_db"),
        charset="utf8mb4",
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
        autocommit=False,
    )
    rows = [
        (
            str(item["market"]),
            Decimal(str(item["trade_price"])),
            float(item["signed_change_rate"]),
            collected_at,
        )
        for item in data_list
    ]

    try:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO coin_prices (symbol, price, change_rate, collected_at)
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    LOGGER.info("collected_at=%s, inserted=%d", collected_at.isoformat(), len(rows))
    return len(rows)


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
    try:
        data = fetch_upbit_data()
        inserted = save_to_db(data)
        LOGGER.info("Upbit 수집 완료: %d개 종목", inserted)
        return 0
    except Exception:
        LOGGER.exception("Upbit 수집 또는 DB 저장에 실패했습니다.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
