"""Built-in tool registry — maps the names in `agent.tools` to real LangChain tools."""
import ast
import logging
import operator
from typing import List, Optional

import httpx
from langchain_core.tools import BaseTool, tool

logger = logging.getLogger("yuno.runtime.tools")


@tool
def web_search(query: str) -> str:
    """Search the web for current information; returns top results (title, snippet, URL)."""
    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception as e:  # noqa: BLE001
        return f"web_search error: {e}"
    if not results:
        return "No results found."
    return "\n\n".join(
        f"{r.get('title', '')}\n{r.get('body', '')}\n{r.get('href', '')}" for r in results
    )


_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (+, -, *, /, **, %, //, parentheses)."""
    try:
        return str(_eval_node(ast.parse(expression, mode="eval").body))
    except Exception as e:  # noqa: BLE001
        return f"calculator error: {e}"


@tool
def http_fetch(url: str) -> str:
    """Fetch a URL via HTTP GET and return the response body text (truncated to 4000 chars)."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        return resp.text[:4000]
    except Exception as e:  # noqa: BLE001
        return f"http_fetch error: {e}"


@tool
def knowledge_search(query: str) -> str:
    """Search the ingested knowledge base (RAG); returns relevant snippets with their sources."""
    from runtime.rag import retrieve

    return retrieve(query)


TOOL_REGISTRY = {
    "web_search": web_search,
    "calculator": calculator,
    "http_fetch": http_fetch,
    "knowledge_search": knowledge_search,
    "rag": knowledge_search,  # alias
}


def get_tools_for(tool_names: Optional[List[str]]) -> List[BaseTool]:
    """Resolve an agent's configured tool names to tool objects (unknown names ignored)."""
    seen, tools = set(), []
    for name in tool_names or []:
        t = TOOL_REGISTRY.get(name)
        if t is not None and t.name not in seen:
            seen.add(t.name)
            tools.append(t)
    return tools
