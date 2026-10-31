from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import TeamMember


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_members(self, owner_user_id: str) -> list[TeamMember]:
        result = await self.session.execute(
            select(TeamMember)
            .where(TeamMember.owner_user_id == owner_user_id)
            .order_by(TeamMember.id)
        )
        return list(result.scalars().all())

    async def add_member(self, owner_user_id: str, email: str) -> TeamMember:
        """Create an invite row. The (owner, email) unique constraint surfaces
        duplicates as IntegrityError - the caller maps it to a 409."""
        member = TeamMember(
            owner_user_id=owner_user_id, invited_email=_normalize_email(email)
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove_member(self, owner_user_id: str, member_id: int) -> bool:
        """Hard delete: every request re-resolves membership from the DB, so
        removal is effective on the member's next API call."""
        result = await self.session.execute(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.owner_user_id == owner_user_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return False
        await self.session.delete(member)
        await self.session.flush()
        return True

    def _activate(self, member: TeamMember, user_id: str) -> None:
        # First matching login binds the row to the member's sub; from then on
        # access follows the user id, so a later email change is harmless.
        member.member_user_id = user_id
        member.status = "active"
        member.activated_at = datetime.now(timezone.utc)

    async def get_membership(
        self, owner_user_id: str, user_id: str, email: str | None = None
    ) -> TeamMember | None:
        """Resolve the caller's membership in ``owner_user_id``'s team, lazily
        activating a pending invite whose email matches the caller's."""
        conditions = [TeamMember.member_user_id == user_id]
        if email:
            conditions.append(
                (TeamMember.member_user_id.is_(None))
                & (TeamMember.invited_email == _normalize_email(email))
            )
        result = await self.session.execute(
            select(TeamMember).where(
                TeamMember.owner_user_id == owner_user_id, or_(*conditions)
            )
        )
        member = result.scalars().first()
        if member is not None and member.member_user_id is None:
            self._activate(member, user_id)
            await self.session.flush()
        return member

    async def list_teams_for_user(
        self, user_id: str, email: str | None = None
    ) -> list[TeamMember]:
        """All memberships for the caller across teams, activating any pending
        email-matched invites in place."""
        conditions = [TeamMember.member_user_id == user_id]
        if email:
            conditions.append(
                (TeamMember.member_user_id.is_(None))
                & (TeamMember.invited_email == _normalize_email(email))
            )
        result = await self.session.execute(
            select(TeamMember)
            .where(or_(*conditions))
            .order_by(TeamMember.created_at, TeamMember.id)
        )
        members = list(result.scalars().all())
        activated = False
        for member in members:
            if member.member_user_id is None:
                self._activate(member, user_id)
                activated = True
        if activated:
            await self.session.flush()
        return members
