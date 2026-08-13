from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import requests

from collector import main


def ticker(symbol: str = "KRW-BTC") -> dict:
    return {"market": symbol, "trade_price": 123.45, "signed_change_rate": 0.0123}


def test_fetch_upbit_data_uses_timeout(monkeypatch):
    response = MagicMock()
    response.json.return_value = [ticker()]
    get = MagicMock(return_value=response)
    monkeypatch.setattr(main.requests, "get", get)

    assert main.fetch_upbit_data(symbols=("KRW-BTC",), timeout=3) == [ticker()]
    response.raise_for_status.assert_called_once()
    assert get.call_args.kwargs["timeout"] == 3


def test_fetch_upbit_data_propagates_http_error(monkeypatch):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("503")
    monkeypatch.setattr(main.requests, "get", MagicMock(return_value=response))

    with pytest.raises(requests.HTTPError):
        main.fetch_upbit_data()


def test_save_to_db_uses_created_at_default_and_batch_insert(monkeypatch):
    monkeypatch.setenv("COLLECTOR_DB_PASSWORD", "test-password")
    cursor = MagicMock()
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(main.pymysql, "connect", MagicMock(return_value=connection))
    collected_at = datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)

    inserted = main.save_to_db([ticker(), ticker("KRW-ETH")], collected_at=collected_at)

    assert inserted == 2
    sql, rows = cursor.executemany.call_args.args
    assert "created_at" not in sql
    assert all(row[-1] == collected_at for row in rows)
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_save_to_db_rolls_back_and_raises(monkeypatch):
    monkeypatch.setenv("COLLECTOR_DB_PASSWORD", "test-password")
    cursor = MagicMock()
    cursor.executemany.side_effect = RuntimeError("db down")
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(main.pymysql, "connect", MagicMock(return_value=connection))

    with pytest.raises(RuntimeError, match="db down"):
        main.save_to_db([ticker()])
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_password_must_not_have_an_insecure_default(monkeypatch):
    monkeypatch.delenv("COLLECTOR_DB_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="COLLECTOR_DB_PASSWORD"):
        main.required_env("COLLECTOR_DB_PASSWORD")
