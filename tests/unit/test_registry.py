from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import ToolResult
from agent.tools.filesystem import list_directory, read_file, search_workspace
from agent.tools.database import query_database
from agent.tools.registry import get_tool, get_tools_for_llm


def test_get_tool_returns_registered_tools() -> None:
    calculator_tool = get_tool("calculator")
    time_tool = get_tool("get_current_time")
    filesystem_tool = get_tool("list_directory")
    read_tool = get_tool("read_file")
    search_tool = get_tool("search_workspace")
    database_tool = get_tool("query_database")

    assert calculator_tool is not None
    assert time_tool is not None
    assert filesystem_tool is not None
    assert calculator_tool.name == "calculator"
    assert calculator_tool.function is calculator
    assert calculator_tool.execute(expression="2 + 2") == ToolResult.ok("4")
    assert time_tool.name == "get_current_time"
    assert time_tool.function is get_current_time
    assert time_tool.execute().success is True
    assert filesystem_tool.name == "list_directory"
    assert filesystem_tool.function is list_directory
    assert read_tool is not None
    assert read_tool.function is read_file
    assert search_tool is not None
    assert search_tool.function is search_workspace
    assert database_tool is not None
    assert database_tool.function is query_database


def test_get_tool_returns_none_for_unknown_name() -> None:
    assert get_tool("missing") is None


def test_registry_exposes_openai_compatible_tool_metadata() -> None:
    tools = get_tools_for_llm()

    assert [item["function"]["name"] for item in tools] == [
        "calculator",
        "get_current_time",
        "list_directory",
        "read_file",
        "search_workspace",
        "query_database",
    ]
    calculator_schema = tools[0]["function"]["parameters"]
    assert calculator_schema["required"] == ["expression"]
    assert calculator_schema["properties"]["expression"]["type"] == "string"
    assert tools[1]["function"]["parameters"]["properties"] == {}
    filesystem_schema = tools[2]["function"]["parameters"]
    assert filesystem_schema["required"] == ["path"]
    assert filesystem_schema["properties"]["path"]["type"] == "string"
    assert tools[3]["function"]["parameters"]["required"] == ["path"]
    assert tools[4]["function"]["parameters"]["required"] == ["query"]
    assert tools[5]["function"]["parameters"]["required"] == ["query"]
