import ast
import math
import operator
from datetime import datetime
from agent.tools.contracts import ToolResult


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _evaluate_expression(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_expression(node.left)
        right = _evaluate_expression(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("o expoente excede o limite permitido")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_expression(node.operand))
    raise ValueError("expressão contém operações não permitidas")


def calculator(expression: str) -> ToolResult:
    try:
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("a expressão está vazia")
        if len(expression) > 200:
            raise ValueError("a expressão excede 200 caracteres")
        result = _evaluate_expression(ast.parse(expression, mode="eval").body)
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("o resultado não é finito")
        return ToolResult.ok(str(result))
    except Exception as error:
        return ToolResult.failure(f"Erro ao calcular: {error}")


def get_current_time() -> ToolResult:
    return ToolResult.ok(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
