from dataclasses import dataclass

@dataclass
class ToolResult:

    success: bool
    content: str

    @classmethod
    def success_result(cls, content: str):
        return cls(
            success=True,
            content=content,
        )

    @classmethod
    def error_result(cls, content: str):
        return cls(
            success=False,
            content=content,
        )