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
    """Registered tool contract consumed by the registry and agent."""

    name: str
    description: str
    parameters: dict[str, Any]

    def execute(self, **arguments: Any) -> ToolResult: ...

    def to_openai_tool(self) -> dict[str, Any]: ...
