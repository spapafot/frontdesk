"""Team management: the account owner invites members who can then work every
site the owner has (tickets, live escalations, knowledge, history, analytics -
everything except site/settings/team management).

Routes are keyed by the caller's own user id, so each account can only ever
manage its own team - "owner-only" is structural, not a role check. Invitation
email delivery happens at the edge: the invite response carries an
``invite_notify`` payload that the Cloudflare Worker strips and turns into an
email (see ``deploy/cloudflare/worker/src/index.ts``).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.repositories.profile_repository import ProfileRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.team import TeamInvite, TeamInviteOut, TeamMemberOut
from app.services import billing, supabase_admin

router = APIRouter(prefix="/team", tags=["team"])


def _to_out(member) -> TeamMemberOut:
    return TeamMemberOut(
        id=member.id,
        email=member.invited_email,
        status=member.status,
        created_at=member.created_at,
        activated_at=member.activated_at,
    )


@router.get("/members", response_model=list[TeamMemberOut])
async def list_members(
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> list[TeamMemberOut]:
    members = await TeamRepository(session).list_members(user.id)
    return [_to_out(m) for m in members]


@router.post("/members", response_model=TeamInviteOut, status_code=201)
async def invite_member(
    body: TeamInvite,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> TeamInviteOut:
    email = body.email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if user.email and email == user.email.strip().lower():
        raise HTTPException(status_code=409, detail="You are the team admin.")

    repo = TeamRepository(session)
    entitlements = await billing.resolve_entitlements(session, user, user.id)
    if entitlements.seats is not None:
        # ``seats`` counts the whole team including the owner, so invited members
        # are capped at ``seats - 1``.
        members = await repo.list_members(user.id)
        if len(members) >= max(entitlements.seats - 1, 0):
            raise HTTPException(
                status_code=402,
                detail="Your plan's team-member limit has been reached. Upgrade to invite more teammates.",
            )
    try:
        member = await repo.add_member(user.id, email)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail=f"{email} has already been invited."
        )

    # Best-effort account creation; the invite row alone already grants access
    # at the invitee's next sign-in (matched by email).
    link = await supabase_admin.generate_invite_link(email)

    # Name the team after the owner's first site so the email reads naturally.
    owned = await ProfileRepository(session).list_for_owner(user.id)
    team_name = owned[0].name if owned else None
    await session.commit()

    detail = link.warning
    if link.already_registered:
        detail = (
            "This person already has an account - they'll see your sites the "
            "next time they sign in."
        )

    return TeamInviteOut(
        member=_to_out(member),
        already_registered=link.already_registered,
        detail=detail,
        invite_notify={
            "email": email,
            "team_name": team_name,
            "invited_by": user.email,
            "action_link": link.action_link,
            "already_registered": link.already_registered,
        },
    )


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: int,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> None:
    removed = await TeamRepository(session).remove_member(user.id, member_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Team member not found.")
    await session.commit()
