from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import ToolResult
from agent.tools.filesystem import list_directory, move_path, read_file, search_workspace
from agent.tools.filesystem import edit_file
from agent.tools.commands import run_command
from agent.tools.conversations import search_conversations
from agent.tools.project_checks import run_project_check
from agent.tools.database import query_database
from agent.tools.registry import get_tool, get_tools_for_llm


def test_get_tool_returns_registered_tools() -> None:
    calculator_tool = get_tool("calculator")
    time_tool = get_tool("get_current_time")
    filesystem_tool = get_tool("list_directory")
    read_tool = get_tool("read_file")
    search_tool = get_tool("search_workspace")
    database_tool = get_tool("query_database")
    move_tool = get_tool("move_path")
    edit_tool = get_tool("edit_file")
    command_tool = get_tool("run_command")
    conversations_tool = get_tool("search_conversations")
    project_check_tool = get_tool("run_project_check")

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
    assert move_tool is not None
    assert move_tool.function is move_path
    assert getattr(move_tool, "requires_confirmation") is True
    assert edit_tool is not None
    assert edit_tool.function is edit_file
    assert edit_tool.requires_confirmation is True
    assert edit_tool.confirmation_preview is not None
    assert command_tool is not None
    assert command_tool.function is run_command
    assert command_tool.requires_confirmation is True
    assert conversations_tool is not None
    assert conversations_tool.function is search_conversations
    assert conversations_tool.requires_confirmation is False
    assert project_check_tool is not None
    assert project_check_tool.function is run_project_check
    assert project_check_tool.requires_confirmation is True
    assert project_check_tool.confirmation_preview is not None


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
        "search_conversations",
        "edit_file",
        "move_path",
        "run_command",
        "run_project_check",
        "search_web",
        "read_webpage",
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
    assert tools[6]["function"]["parameters"]["required"] == ["query"]
    assert tools[7]["function"]["parameters"]["required"] == ["path", "old_text", "new_text"]
    assert tools[8]["function"]["parameters"]["required"] == ["source", "destination"]
    assert tools[9]["function"]["parameters"]["required"] == ["argv"]
    assert tools[10]["function"]["parameters"]["required"] == ["check_name"]
    assert tools[11]["function"]["parameters"]["required"] == ["query"]
    assert tools[12]["function"]["parameters"]["required"] == ["url"]
