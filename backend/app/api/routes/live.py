from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import SiteAccess, get_selected_site, get_site_access
from app.core.auth import AdminUser, require_admin
from app.core.config import settings
from app.core.db import get_session
from app.models.conversation import Conversation, EscalationTicket
from app.models.profile import AssistantProfile
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.live_repository import LiveRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.team_repository import TeamRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.live import (
    CallbackArchiveRequest,
    CallbackAssignRequest,
    CallbackStatusRequest,
    CallbackTicketOut,
    InternalActionRequest,
    InternalAuthorizeRequest,
    LiveActor,
    OperatorOut,
    OperatorSocketTicketRequest,
    SocketTicketOut,
    VisitorSocketTicketRequest,
)
from app.services.live_auth import (
    conversation_token_matches,
    create_socket_ticket,
    decode_socket_ticket,
)
from app.services.widget_auth import decode_widget_token

router = APIRouter(tags=["live support"])


def _require_global() -> None:
    if not settings.live_human_escalation_enabled:
        raise HTTPException(status_code=404, detail="Live support is unavailable.")


def _require_profile(profile: AssistantProfile | None) -> AssistantProfile:
    _require_global()
    if profile is None or not profile.live_human_escalation_enabled:
        raise HTTPException(status_code=404, detail="Live support is unavailable.")
    return profile


def _ticket_out(ticket: EscalationTicket) -> CallbackTicketOut:
    return CallbackTicketOut.model_validate(ticket, from_attributes=True)


async def _operator_can_access(
    profile: AssistantProfile, user_id: str | None, session: AsyncSession
) -> bool:
    """Owner or activated team member. Socket-ticket claims carry only the
    user id (no email) - correct, because a member must have made a REST call
    (which activates their membership) to obtain a socket ticket at all."""
    if not user_id:
        return False
    if profile.owner_user_id == user_id:
        return True
    membership = await TeamRepository(session).get_membership(
        profile.owner_user_id, user_id
    )
    return membership is not None


def _conversation_state(conversation: Conversation, messages: list[Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "conversation_id": conversation.id,
        "profile_id": conversation.profile_id,
        "mode": conversation.mode,
        "assigned_user_id": conversation.assigned_user_id,
        "escalation_requested_at": conversation.escalation_requested_at,
        "escalation_expires_at": conversation.escalation_expires_at,
        "accepted_at": conversation.accepted_at,
        "closed_at": conversation.closed_at,
    }
    if messages is not None:
        state["messages"] = [
            {
                "id": message.id,
                "client_message_id": message.client_message_id,
                "role": message.role,
                "content": message.content,
                "sender_type": message.sender_type,
                "sender_user_id": message.sender_user_id,
                "sender_display_name": message.sender_display_name,
                "created_at": message.created_at,
            }
            for message in messages
            if message.content
        ]
    return state


@router.post("/live/visitor/socket-ticket", response_model=SocketTicketOut)
async def visitor_socket_ticket(
    body: VisitorSocketTicketRequest,
    session: AsyncSession = Depends(get_session),
) -> SocketTicketOut:
    _require_global()
    profile_id, installation_id, public_key = decode_widget_token(body.widget_token)
    installation = await WidgetRepository(session).get_for_profile(profile_id)
    if (
        installation is None
        or installation.id != installation_id
        or installation.public_key != public_key
        or not installation.is_enabled
    ):
        raise HTTPException(status_code=401, detail="Widget installation is unavailable.")
    profile = _require_profile(await ProfileRepository(session).get(profile_id))
    conversation = await ConversationRepository(session).get(body.conversation_id)
    if conversation is None or conversation.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conversation_token_matches(
        body.conversation_token,
        profile_id=profile.id,
        conversation_id=conversation.id,
        stored_hash=conversation.visitor_session_id_hash,
    )
    claims = {
        "actor_type": "visitor",
        "profile_id": profile.id,
        "conversation_id": conversation.id,
        "channel": "conversation",
    }
    return SocketTicketOut(
        ticket=create_socket_ticket(claims),
        websocket_path=f"/live/conversations/{conversation.id}",
        conversation_id=conversation.id,
        expires_in=settings.live_socket_ticket_ttl_seconds,
    )


@router.post("/live/operator/socket-ticket", response_model=SocketTicketOut)
async def operator_socket_ticket(
    body: OperatorSocketTicketRequest,
    user: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SocketTicketOut:
    access = await ProfileRepository(session).get_accessible(
        body.site_id, user.id, user.email
    )
    profile = _require_profile(access[0] if access else None)
    await session.commit()  # persist a lazy invite activation, if any
    if body.channel == "conversation":
        if body.conversation_id is None:
            raise HTTPException(status_code=422, detail="conversation_id is required.")
        conversation = await ConversationRepository(session).get(body.conversation_id)
        if conversation is None or conversation.profile_id != profile.id:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        path = f"/live/conversations/{conversation.id}"
    else:
        path = f"/live/inbox/{profile.id}"
    claims = {
        "actor_type": "operator",
        "profile_id": profile.id,
        "conversation_id": body.conversation_id,
        "user_id": user.id,
        "display_name": user.email or "Support agent",
        "channel": body.channel,
    }
    return SocketTicketOut(
        ticket=create_socket_ticket(claims),
        websocket_path=path,
        conversation_id=body.conversation_id,
        expires_in=settings.live_socket_ticket_ttl_seconds,
    )


@router.post("/internal/live/authorize")
async def internal_authorize(
    body: InternalAuthorizeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_global()
    claims = decode_socket_ticket(body.ticket)
    actor = LiveActor.model_validate(claims)
    profile = _require_profile(await ProfileRepository(session).get(actor.profile_id))
    if actor.actor_type == "operator" and not await _operator_can_access(
        profile, actor.user_id, session
    ):
        raise HTTPException(
            status_code=403, detail="Operator no longer has access to this site."
        )
    if actor.channel == "conversation":
        conversation = await ConversationRepository(session).get(actor.conversation_id or 0)
        if conversation is None or conversation.profile_id != profile.id:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    return actor.model_dump()


async def _authorized_conversation(
    actor: LiveActor, session: AsyncSession
) -> tuple[AssistantProfile, Conversation, ConversationRepository, LiveRepository]:
    profile = _require_profile(await ProfileRepository(session).get(actor.profile_id))
    if actor.actor_type == "operator" and not await _operator_can_access(
        profile, actor.user_id, session
    ):
        raise HTTPException(
            status_code=403, detail="Operator no longer has access to this site."
        )
    conversation_repo = ConversationRepository(session)
    conversation = await conversation_repo.get(actor.conversation_id or 0)
    if conversation is None or conversation.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return profile, conversation, conversation_repo, LiveRepository(session)


@router.post("/internal/live/action")
async def internal_action(
    body: InternalActionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor = body.actor
    profile, conversation, conversation_repo, live_repo = await _authorized_conversation(actor, session)
    now = datetime.now(timezone.utc)

    if body.action == "state":
        return _conversation_state(
            conversation, await conversation_repo.get_messages(conversation.id)
        )

    if body.action == "escalate":
        if actor.actor_type != "visitor":
            raise HTTPException(status_code=403, detail="Only the visitor can request support.")
        expires_at = now + timedelta(
            seconds=settings.live_accept_timeout_seconds
        )
        transitioned_conversation = await live_repo.escalate(
            conversation.id, requested_at=now, expires_at=expires_at
        )
        transitioned = transitioned_conversation is not None
        if transitioned_conversation is not None:
            conversation = transitioned_conversation
            await live_repo.add_event(conversation.id, "escalation_requested", "visitor")
        else:
            await session.refresh(conversation)
        await session.commit()
        return {**_conversation_state(conversation), "transitioned": transitioned}

    elif body.action == "cancel":
        if actor.actor_type != "visitor":
            raise HTTPException(status_code=409, detail="Escalation is not waiting.")
        cancelled = await live_repo.cancel(conversation.id)
        if cancelled is None:
            raise HTTPException(status_code=409, detail="Escalation is not waiting.")
        conversation = cancelled
        await live_repo.add_event(conversation.id, "escalation_cancelled", "visitor")

    elif body.action == "accept":
        if actor.actor_type != "operator" or not actor.user_id:
            raise HTTPException(status_code=403, detail="Only an operator can accept.")
        accepted = await live_repo.accept(conversation.id, actor.user_id)
        if accepted is None:
            raise HTTPException(status_code=409, detail="Conversation is no longer available.")
        conversation = accepted
        await live_repo.add_event(
            conversation.id, "accepted", "operator", actor.user_id,
            {"display_name": actor.display_name},
        )

    elif body.action == "message":
        if conversation.mode != "human":
            raise HTTPException(status_code=409, detail="Conversation is not in human mode.")
        if actor.actor_type == "operator" and conversation.assigned_user_id != actor.user_id:
            raise HTTPException(status_code=403, detail="Conversation is assigned to another operator.")
        content = str(body.payload.get("content", "")).strip()
        client_message_id = str(body.payload.get("client_message_id", ""))
        if not content or len(content) > 4000 or not client_message_id or len(client_message_id) > 36:
            raise HTTPException(status_code=422, detail="A valid message and client_message_id are required.")
        message, created = await live_repo.add_message_idempotent(
            conversation_id=conversation.id,
            client_message_id=client_message_id,
            role="assistant" if actor.actor_type == "operator" else "user",
            content=content,
            sender_type=actor.actor_type,
            sender_user_id=actor.user_id,
            sender_display_name=actor.display_name,
        )
        await session.commit()
        return {
            "message": {
                "id": message.id,
                "client_message_id": message.client_message_id,
                "role": message.role,
                "content": message.content,
                "sender_type": message.sender_type,
                "sender_user_id": message.sender_user_id,
                "sender_display_name": message.sender_display_name,
                "created_at": message.created_at,
            },
            "created": created,
        }

    elif body.action == "close":
        if (
            actor.actor_type != "operator"
            or not actor.user_id
            or conversation.assigned_user_id != actor.user_id
        ):
            raise HTTPException(status_code=403, detail="Only the assigned operator can close.")
        closed = await live_repo.close(conversation.id, actor.user_id, now)
        if closed is None:
            raise HTTPException(status_code=409, detail="Conversation is not open.")
        conversation = closed
        await live_repo.add_event(conversation.id, "closed", "operator", actor.user_id)

    elif body.action == "timeout":
        timed_out = await live_repo.timeout(conversation.id, now)
        if timed_out is not None:
            conversation = timed_out
            await live_repo.add_event(conversation.id, "escalation_timed_out", "system")
        else:
            # Not expired (or already transitioned): report fresh state so the
            # Durable Object alarm can decide whether to retry or stand down.
            await session.refresh(conversation)

    elif body.action == "unavailable":
        if actor.actor_type != "system":
            raise HTTPException(status_code=403, detail="Action is unavailable.")
        transitioned = await live_repo.mark_unavailable(conversation.id, now)
        if transitioned is not None:
            conversation = transitioned
            await live_repo.add_event(conversation.id, "no_operator_available", "system")
        else:
            await session.refresh(conversation)

    elif body.action == "ticket":
        if actor.actor_type != "visitor" or conversation.mode != "pending_ticket":
            raise HTTPException(status_code=409, detail="Callback is not available.")
        email = str(body.payload.get("customer_email", "")).strip()
        if "@" not in email or len(email) > 254:
            raise HTTPException(status_code=422, detail="A valid email is required.")
        ticket = await live_repo.create_ticket(
            conversation_id=conversation.id,
            profile_id=conversation.profile_id,
            customer_email=email,
            customer_name=(str(body.payload.get("customer_name", "")).strip() or None),
            customer_message=(str(body.payload.get("customer_message", "")).strip() or None),
        )
        conversation.mode = "closed"
        conversation.closed_at = now
        await live_repo.add_event(conversation.id, "callback_requested", "visitor")
        await session.commit()
        result: dict[str, Any] = {"ticket": _ticket_out(ticket), **_conversation_state(conversation)}
        if profile.notification_email:
            # Owner-only routing data: the Worker consumes this to send the
            # ticket notification email and strips it before any broadcast.
            result["notify"] = {
                "email": profile.notification_email,
                "site_name": profile.name,
            }
        return result

    await session.commit()
    return _conversation_state(conversation)


@router.get("/live/callbacks", response_model=list[CallbackTicketOut])
async def list_callbacks(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[CallbackTicketOut]:
    _require_profile(profile)
    return [_ticket_out(item) for item in await LiveRepository(session).list_tickets(profile.id)]


@router.get("/live/operators", response_model=list[OperatorOut])
async def list_operators(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> list[OperatorOut]:
    """Assignable operators: the owner plus activated team members. Unlike
    /team/members this is member-callable, so any operator can populate the
    board's assignee picker."""
    _require_profile(profile)
    operators = [
        OperatorOut(
            user_id=profile.owner_user_id,
            email=profile.notification_email,
            is_owner=True,
        )
    ]
    members = await TeamRepository(session).list_members(profile.owner_user_id)
    operators.extend(
        OperatorOut(user_id=member.member_user_id, email=member.invited_email, is_owner=False)
        for member in members
        if member.status == "active" and member.member_user_id is not None
    )
    return operators


@router.post("/live/callbacks/{ticket_id}/status", response_model=CallbackTicketOut)
async def set_callback_status(
    ticket_id: int,
    body: CallbackStatusRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
    user: AdminUser = Depends(require_admin),
) -> CallbackTicketOut:
    _require_profile(profile)
    ticket = await LiveRepository(session).set_ticket_status(
        ticket_id, profile.id, body.status, actor_user_id=user.id
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Callback not found.")
    await session.commit()
    return _ticket_out(ticket)


@router.post("/live/callbacks/{ticket_id}/assignee", response_model=CallbackTicketOut)
async def assign_callback(
    ticket_id: int,
    body: CallbackAssignRequest,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> CallbackTicketOut:
    _require_profile(profile)
    if body.assignee_user_id is not None and not await _operator_can_access(
        profile, body.assignee_user_id, session
    ):
        raise HTTPException(
            status_code=422, detail="Assignee is not a member of this site's team."
        )
    ticket = await LiveRepository(session).assign_ticket(
        ticket_id, profile.id, body.assignee_user_id
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Callback not found.")
    await session.commit()
    return _ticket_out(ticket)


@router.post("/live/callbacks/{ticket_id}/archive", response_model=CallbackTicketOut)
async def archive_callback(
    ticket_id: int,
    body: CallbackArchiveRequest,
    session: AsyncSession = Depends(get_session),
    access: SiteAccess = Depends(get_site_access),
) -> CallbackTicketOut:
    _require_profile(access.profile)
    if not access.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the site owner can archive tickets.",
        )
    repo = LiveRepository(session)
    ticket = await repo.get_ticket(ticket_id, access.profile.id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Callback not found.")
    if body.archived and ticket.status != "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only resolved tickets can be archived.",
        )
    ticket = await repo.set_ticket_archived(ticket_id, access.profile.id, body.archived)
    await session.commit()
    return _ticket_out(ticket)


# Kept for admin bundles deployed before the board UI; delegates to the
# status workflow so resolution semantics stay in one place.
@router.post("/live/callbacks/{ticket_id}/resolve", response_model=CallbackTicketOut)
async def resolve_callback(
    ticket_id: int,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
    user: AdminUser = Depends(require_admin),
) -> CallbackTicketOut:
    _require_profile(profile)
    ticket = await LiveRepository(session).set_ticket_status(
        ticket_id, profile.id, "resolved", actor_user_id=user.id
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Callback not found.")
    await session.commit()
    return _ticket_out(ticket)
