from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolResult:
    """Structured outcome returned by a tool."""

    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def failure(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error)


class Tool(Protocol):
    """Callable tool contract; registered names live in the registry keys."""

    @property
    def __name__(self) -> str: ...

    def __call__(self, *args: Any, **kwargs: Any) -> ToolResult: ...
