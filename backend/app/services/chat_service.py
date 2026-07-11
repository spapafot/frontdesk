import json
from collections.abc import AsyncGenerator
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.db import SessionLocal
from app.prompts.system_prompt import build_system_prompt
from app.repositories.profile_repository import ProfileRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services.rag_service import search_knowledge

# Injected just before the user's question so the model answers from retrieved
# context in a single streaming call (no tool round-trips).
KB_CONTEXT_TEMPLATE = (
    "Here is the information available to answer the customer's current question. It may "
    "come from several sources, be in any order, and include unrelated material - read "
    "all of it and use the parts that are relevant. Rely ONLY on this information; if the "
    "answer cannot be determined from it, say you do not have that information."
    "\n---\n{context}\n---"
)
NO_CONTEXT_NOTE = (
    "No relevant information was found for the customer's current question. If you "
    "cannot answer it from the earlier conversation, say you do not have that "
    "information."
)
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


async def _resolve_conversation(
    repo: ConversationRepository, profile_id: int, conversation_id: int | None
):
    conversation = await repo.get(conversation_id) if conversation_id else None
    if conversation is None or conversation.profile_id != profile_id:
        conversation = await repo.create(profile_id)
    return conversation


async def run_turn(
    message: str,
    profile_id: int,
    conversation_id: int | None = None,
) -> AsyncGenerator[dict, None]:
    """Run one assistant turn, yielding structured events.

    Transport-agnostic core used by the SSE chat route. Events are dicts of the form
    ``{"type": "conversation"|"sources"|"token"|"done"|"error", ...}``.

    ``profile_id`` is resolved and authorized by the transport layer.
    """
    async with SessionLocal() as session:
        profile_repo = ProfileRepository(session)
        conversation_repo = ConversationRepository(session)

        profile = await profile_repo.get(profile_id)
        if profile is None:
            yield {"type": "error", "message": "Assistant profile not found."}
            return

        conversation = await _resolve_conversation(
            conversation_repo, profile.id, conversation_id
        )
        if not conversation.title:
            conversation.title = message.strip()[:120] or None
        await session.commit()

        yield {"type": "conversation", "conversation_id": conversation.id}

        if not settings.deepseek_api_key:
            yield {"type": "error", "message": "DEEPSEEK_API_KEY is not configured."}
            return

        tz = ZoneInfo(profile.timezone)
        now = datetime.now(tz)
        system_prompt = build_system_prompt(
            business_name=profile.name,
            assistant_name=profile.assistant_name,
            now=now.strftime("%A %Y-%m-%d %H:%M"),
            timezone=profile.timezone,
            custom_instructions=profile.custom_instructions,
        )

        history = await _load_history(conversation_repo, conversation.id)
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # RAG-always: retrieve the relevant knowledge up front so the model can answer
        # in a single streaming call instead of multiple blocking tool round-trips.
        results = await search_knowledge(session, profile.id, message)
        had_sources = bool(results)
        sources = [
            {
                "title": r.get("title"),
                "score": r.get("score"),
                "snippet": (r.get("content") or "")[:200],
            }
            for r in results
        ]
        if results:
            context_block = "\n\n".join(
                f"[{r.get('title') or 'Document'}]\n{r.get('content') or ''}"
                for r in results
            )
            messages.append(
                {"role": "system", "content": KB_CONTEXT_TEMPLATE.format(context=context_block)}
            )
        else:
            messages.append({"role": "system", "content": NO_CONTEXT_NOTE})

        messages.append({"role": "user", "content": message})
        await conversation_repo.add_message(conversation.id, "user", message)
        await session.commit()

        client = get_client()

        # DeepSeek V4 thinking-mode toggle (passed through the OpenAI-compatible API).
        extra_body = {
            "thinking": {"type": "enabled" if settings.deepseek_thinking else "disabled"}
        }

        try:
            if sources:
                yield {"type": "sources", "sources": sources}

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
                    yield {"type": "token", "content": delta}

            await conversation_repo.add_message(
                conversation.id,
                "assistant",
                final_text,
                meta={
                    "answered": had_sources,
                    "searched": True,
                    "had_sources": had_sources,
                    "question": message[:500],
                },
            )
            await session.commit()
            yield {"type": "done", "conversation_id": conversation.id}
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            yield {"type": "error", "message": f"Assistant error: {exc}"}


async def stream_chat(
    message: str,
    profile_id: int,
    conversation_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """SSE wrapper over ``run_turn`` for the HTTP chat endpoint."""
    async for event in run_turn(message, profile_id, conversation_id):
        yield _sse(event)
