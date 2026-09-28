"""Read-only search over explicitly requested saved conversation history."""

from agent.core.history import ConversationHistory
from agent.tools.contracts import ToolResult

_MAX_QUERY_CHARS = 200


def search_conversations(query: str, max_results: int = 5) -> ToolResult:
    """Search prior conversations and return a small number of text excerpts."""
    if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY_CHARS:
        return ToolResult.failure("A busca precisa conter entre 1 e 200 caracteres.")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 5:
        return ToolResult.failure("max_results deve estar entre 1 e 5.")

    results = ConversationHistory().search_conversations(
        query=query,
        limit=max_results,
    )
    if not results:
        return ToolResult.ok("Nenhum trecho correspondente foi encontrado nas conversas anteriores.")
    return ToolResult.ok(results)
