from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_selected_site
from app.core.config import settings
from app.core.db import get_session
from app.models.profile import AssistantProfile
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import (
    ConversationOut,
    MessageOut,
    RatingRequest,
    RenameRequest,
)
from app.services.summary_service import summarize_conversation

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_out(conversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        started_at=conversation.started_at,
        rating=conversation.rating,
        summary=(
            conversation.summary if settings.conversation_summaries_enabled else None
        ),
        mode=conversation.mode,
        assigned_user_id=conversation.assigned_user_id,
        escalation_requested_at=conversation.escalation_requested_at,
        accepted_at=conversation.accepted_at,
        closed_at=conversation.closed_at,
        last_message_at=conversation.last_message_at,
        is_visitor=conversation.visitor_session_id_hash is not None,
    )


async def _get_owned(conversation_id: int, profile_id: int, session: AsyncSession):
    repo = ConversationRepository(session)
    conversation = await repo.get(conversation_id)
    if conversation is None or conversation.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return repo, conversation


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[ConversationOut]:
    conversations = await ConversationRepository(session).list_conversations(profile.id)
    return [_to_out(c) for c in conversations]


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: int,
    body: RenameRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> ConversationOut:
    repo, conversation = await _get_owned(conversation_id, profile.id, session)
    await repo.rename(conversation, body.title.strip())
    await session.commit()
    return _to_out(conversation)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> None:
    repo, conversation = await _get_owned(conversation_id, profile.id, session)
    await repo.delete(conversation)
    await session.commit()


@router.post("/{conversation_id}/rating", response_model=ConversationOut)
async def rate_conversation(
    conversation_id: int,
    body: RatingRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> ConversationOut:
    repo, conversation = await _get_owned(conversation_id, profile.id, session)
    await repo.set_rating(conversation, body.rating)
    await session.commit()
    return _to_out(conversation)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> ConversationOut:
    repo, conversation = await _get_owned(conversation_id, profile.id, session)
    if settings.conversation_summaries_enabled and not conversation.summary:
        messages = await repo.get_messages(conversation_id)
        history = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant") and m.content
        ]
        if history:
            summary = await summarize_conversation(history)
            if summary:
                await repo.set_summary(conversation, summary)
                await session.commit()
    return _to_out(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[MessageOut]:
    repo = ConversationRepository(session)
    conversation = await repo.get(conversation_id)
    if conversation is None or conversation.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = await repo.get_messages(conversation_id)
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            sender_type=m.sender_type,
            sender_display_name=m.sender_display_name,
            created_at=m.created_at,
        )
        for m in messages
        if m.role in ("user", "assistant") and m.content
    ]
