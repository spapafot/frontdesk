import json
from collections.abc import AsyncGenerator
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.db import SessionLocal
from app.prompts.system_prompt import build_system_prompt
from app.repositories.business_repository import BusinessRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services import tool_service


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def _load_history(repo: ConversationRepository, conversation_id: int) -> list[dict]:
    history: list[dict] = []
    for message in await repo.get_messages(conversation_id):
        if message.role in ("user", "assistant") and message.content:
            history.append({"role": message.role, "content": message.content})
    return history


async def stream_chat(
    message: str,
    conversation_id: int | None = None,
    business_id: int | None = None,
) -> AsyncGenerator[str, None]:
    async with SessionLocal() as session:
        business_repo = BusinessRepository(session)
        conversation_repo = ConversationRepository(session)

        business = (
            await business_repo.get(business_id)
            if business_id
            else await business_repo.get_or_create_default()
        )
        if business is None:
            yield _sse({"type": "error", "message": "No business configured."})
            return
        await session.commit()

        if conversation_id:
            conversation = await conversation_repo.get(conversation_id)
            if conversation is None:
                conversation = await conversation_repo.create(business.id)
        else:
            conversation = await conversation_repo.create(business.id)
        if not conversation.title:
            conversation.title = message.strip()[:120] or None
        await session.commit()

        yield _sse({"type": "conversation", "conversation_id": conversation.id})

        if not settings.deepseek_api_key:
            yield _sse({"type": "error", "message": "DEEPSEEK_API_KEY is not configured."})
            return

        tz = ZoneInfo(business.timezone)
        now = datetime.now(tz)
        system_prompt = build_system_prompt(
            business_name=business.name,
            assistant_name=business.assistant_name,
            now=now.strftime("%A %Y-%m-%d %H:%M"),
            timezone=business.timezone,
            custom_instructions=business.custom_instructions,
        )

        history = await _load_history(conversation_repo, conversation.id)
        messages: list[dict] = [{"role": "system", "content": system_prompt}, *history]
        messages.append({"role": "user", "content": message})
        await conversation_repo.add_message(conversation.id, "user", message)
        await session.commit()

        client = get_client()
        sources: list[dict] = []
        searched = False

        # DeepSeek V4 thinking-mode toggle (passed through the OpenAI-compatible API).
        extra_body = {
            "thinking": {"type": "enabled" if settings.deepseek_thinking else "disabled"}
        }

        try:
            for _ in range(settings.max_tool_iterations):
                response = await client.chat.completions.create(
                    model=settings.deepseek_model,
                    messages=messages,
                    tools=tool_service.TOOL_SCHEMAS,
                    tool_choice="auto",
                    extra_body=extra_body,
                )
                choice = response.choices[0].message
                if not choice.tool_calls:
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": choice.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.tool_calls
                        ],
                    }
                )

                for tool_call in choice.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    result = await tool_service.dispatch(
                        name, args, session, business.id, now
                    )
                    yield _sse({"type": "tool_call", "name": name, "arguments": args, "result": result})

                    if name == "search_knowledge_base":
                        searched = True
                        for item in result.get("results", []):
                            sources.append(
                                {
                                    "title": item.get("title"),
                                    "score": item.get("score"),
                                    "snippet": item.get("content", "")[:200],
                                }
                            )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, default=str),
                        }
                    )
                    await conversation_repo.add_message(
                        conversation.id,
                        "tool",
                        json.dumps(result, default=str),
                        tool_name=name,
                        meta={"arguments": args},
                    )
                await session.commit()

            if sources:
                yield _sse({"type": "sources", "sources": sources})

            final_text = ""
            stream = await client.chat.completions.create(
                model=settings.deepseek_model,
                messages=messages,
                stream=True,
                extra_body=extra_body,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    final_text += delta
                    yield _sse({"type": "token", "content": delta})

            await conversation_repo.add_message(
                conversation.id,
                "assistant",
                final_text,
                meta={
                    "answered": bool(sources) or not searched,
                    "searched": searched,
                    "had_sources": bool(sources),
                    "question": message[:500],
                },
            )
            await session.commit()
            yield _sse({"type": "done", "conversation_id": conversation.id})
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            yield _sse({"type": "error", "message": f"Assistant error: {exc}"})
