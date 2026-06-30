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
# Added for voice turns so the reply is short enough to be read aloud quickly.
VOICE_STYLE_NOTE = (
    "This conversation is spoken aloud. Answer in at most 1-3 short sentences, in "
    "plain words, with no lists, headings, or symbols."
)


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def _load_history(
    repo: ConversationRepository, conversation_id: int, limit: int | None = None
) -> list[dict]:
    history: list[dict] = []
    for message in await repo.get_messages(conversation_id):
        if message.role in ("user", "assistant") and message.content:
            history.append({"role": message.role, "content": message.content})
    # For voice, keep only the most recent turns so the prompt stays small.
    if limit is not None and len(history) > limit:
        history = history[-limit:]
    return history


async def run_turn(
    message: str,
    conversation_id: int | None = None,
    business_id: int | None = None,
    site_key: str | None = None,
    voice: bool = False,
) -> AsyncGenerator[dict, None]:
    """Run one assistant turn, yielding structured events.

    Transport-agnostic core shared by the SSE chat route (``stream_chat``) and
    the voice WebSocket handler. Events are dicts of the form
    ``{"type": "conversation"|"sources"|"token"|"done"|"error", ...}``.

    Tenant resolution order: explicit ``site_key`` (used by the embeddable
    widget), then ``business_id``, then the single default business.
    """
    async with SessionLocal() as session:
        business_repo = BusinessRepository(session)
        conversation_repo = ConversationRepository(session)

        if site_key:
            business = await business_repo.get_by_public_key(site_key)
            if business is None:
                yield {"type": "error", "message": "Invalid site key."}
                return
        elif business_id:
            business = await business_repo.get(business_id)
        else:
            business = await business_repo.get_or_create_default()
        if business is None:
            yield {"type": "error", "message": "No business configured."}
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

        yield {"type": "conversation", "conversation_id": conversation.id}

        if not settings.deepseek_api_key:
            yield {"type": "error", "message": "DEEPSEEK_API_KEY is not configured."}
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

        history_limit = settings.voice_history_messages if voice else None
        history = await _load_history(conversation_repo, conversation.id, history_limit)
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if voice:
            messages.append({"role": "system", "content": VOICE_STYLE_NOTE})
        messages.extend(history)

        # RAG-always: retrieve the relevant knowledge up front so the model can answer
        # in a single streaming call instead of multiple blocking tool round-trips.
        # Voice turns retrieve fewer chunks to keep the prompt small and fast.
        rag_limit = settings.voice_rag_top_k if voice else None
        results = await search_knowledge(session, business.id, message, limit=rag_limit)
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
    conversation_id: int | None = None,
    business_id: int | None = None,
    site_key: str | None = None,
    voice: bool = False,
) -> AsyncGenerator[str, None]:
    """SSE wrapper over ``run_turn`` for the HTTP chat endpoint."""
    async for event in run_turn(message, conversation_id, business_id, site_key, voice):
        yield _sse(event)
