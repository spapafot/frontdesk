from datetime import datetime

from pydantic import BaseModel, Field


class TeamInvite(BaseModel):
    # Deliberately not EmailStr: the email-validator package is not a backend
    # dependency. The route checks for a plausible address; Supabase validates
    # for real when the account is created.
    email: str = Field(..., min_length=3, max_length=254)


class TeamMemberOut(BaseModel):
    id: int
    email: str
    status: str  # invited | active
    created_at: datetime
    activated_at: datetime | None = None


class TeamInviteOut(BaseModel):
    member: TeamMemberOut
    already_registered: bool = False
    # Human-readable degradation notice (e.g. service key unconfigured).
    detail: str | None = None
    # Owner-only payload consumed AND STRIPPED by the edge Worker, which sends
    # the invitation email via Cloudflare Email Sending. Carries the one-time
    # set-password action link, so it must never reach a browser in production.
    invite_notify: dict | None = None
