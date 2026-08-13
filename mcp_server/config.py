import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from dotenv import load_dotenv


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} 환경변수가 필요합니다.")
    return value


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name}은(는) 정수여야 합니다.") from error

    if value < minimum or value > maximum:
        raise ValueError(f"{name}은(는) {minimum}~{maximum} 범위여야 합니다.")
    return value


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_connect_timeout: int
    mcp_auth_token: str
    mcp_server_url: str
    mcp_host: str
    mcp_port: int
    max_top_gainers_limit: int
    max_history_hours: int
    max_history_rows: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        token = _required("MCP_AUTH_TOKEN")
        if len(token) < 16:
            raise ValueError("MCP_AUTH_TOKEN은 최소 16자여야 합니다.")

        server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp").strip()
        parsed_url = urlparse(server_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("MCP_SERVER_URL은 http(s) URL이어야 합니다.")

        return cls(
            db_host=os.getenv("DB_HOST", "localhost").strip(),
            db_port=_bounded_int("DB_PORT", 3306, 1, 65535),
            db_name=os.getenv("DB_NAME", "crypto_db").strip(),
            db_user=os.getenv("MCP_DB_USER", "mcp_user").strip(),
            db_password=_required("MCP_DB_PASSWORD"),
            db_connect_timeout=_bounded_int("DB_CONNECT_TIMEOUT", 5, 1, 30),
            mcp_auth_token=token,
            mcp_server_url=server_url.rstrip("/"),
            mcp_host=os.getenv("MCP_HOST", "0.0.0.0").strip(),
            mcp_port=_bounded_int("MCP_PORT", 8000, 1, 65535),
            max_top_gainers_limit=_bounded_int("MAX_TOP_GAINERS_LIMIT", 20, 1, 100),
            max_history_hours=_bounded_int("MAX_HISTORY_HOURS", 168, 1, 744),
            max_history_rows=_bounded_int("MAX_HISTORY_ROWS", 500, 1, 5000),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
