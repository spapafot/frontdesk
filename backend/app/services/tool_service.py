from datetime import datetime
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools import knowledge_tools

ToolFn = Callable[..., Awaitable[dict]]

# Registry: tool name -> callable
_REGISTRY: dict[str, ToolFn] = {
    "search_knowledge_base": knowledge_tools.search_knowledge_base,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Search the company's knowledge base (the uploaded documents) for "
                "information needed to answer the customer's question. Use this for "
                "every question that requires company-specific information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The customer's question or the topic to look up.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


async def dispatch(
    name: str,
    arguments: dict[str, Any],
    session: AsyncSession,
    business_id: int,
    now: datetime,
) -> dict:
    fn = _REGISTRY.get(name)
    if fn is None:
        return {"error": "unknown_tool", "message": f"Tool '{name}' is not registered."}
    try:
        return await fn(session, business_id, now, **arguments)
    except TypeError as exc:
        return {"error": "bad_arguments", "message": str(exc)}
