from pydantic import BaseModel


class PasswordRecoveryRequest(BaseModel):
    email: str


class RecoveryNotify(BaseModel):
    """Owner-only payload the Cloudflare Worker strips and emails; the browser
    never sees it. ``action_link`` is a live credential - it must never appear
    anywhere else in the response or in logs."""

    email: str
    action_link: str | None = None


class PasswordRecoveryOut(BaseModel):
    detail: str
    recovery_notify: RecoveryNotify
