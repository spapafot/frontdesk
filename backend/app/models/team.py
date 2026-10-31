from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TeamMember(Base):
    """One invited member of an account's team.

    The team is keyed by the admin's Supabase ``sub`` (``owner_user_id``) - the
    same value that scopes ``assistant_profiles`` - so membership grants access
    to every site the admin owns. Rows are created from an email invite and
    bound to the member's own ``sub`` on their first matching login; after
    binding, access follows the user id, never the email again.
    """

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "invited_email", name="uq_team_members_owner_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    # Always stored lowercased/stripped; compared against the JWT email claim.
    invited_email: Mapped[str] = mapped_column(String(254), index=True)
    member_user_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="invited", server_default="invited"
    )  # invited | active
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
