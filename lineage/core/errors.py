"""Structured library errors, independent of storage and transports."""

from copy import deepcopy
from typing import TypeAlias

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]


class LineageError(Exception):
    """A stable error code and detached JSON diagnostic data."""

    def __init__(self, code: str, detail: JSONValue = None) -> None:
        self.code = code
        self.detail = deepcopy(detail)
        super().__init__(code)

    def as_dict(self) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {"ok": False, "code": self.code}
        if self.detail is not None:
            result["detail"] = deepcopy(self.detail)
        return result


def error_payload(exc: 'LineageError') -> dict:
    """A-U03-2 (orchestrator): public error envelope helper used by the HTTP host."""
    return exc.as_dict()
