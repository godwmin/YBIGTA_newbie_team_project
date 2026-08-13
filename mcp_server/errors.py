from enum import Enum


class ErrorCode(str, Enum):
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_LIMIT = "INVALID_LIMIT"
    INVALID_HOURS = "INVALID_HOURS"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """An expected error whose message is safe to return to an MCP client."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
