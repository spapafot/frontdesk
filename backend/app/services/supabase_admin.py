"""Create invited users via the Supabase Admin API (service-role key).

Only ``generate_link`` is used: it creates the account and returns a one-time
set-password action link WITHOUT Supabase sending any email — delivery happens
at the edge via Cloudflare Email Sending (see the Worker's invite interception).

Best-effort by design: the membership row is the real access mechanism (it
activates by email match at the member's first login), so a failure here must
never fail the invite request. Nothing in this module may log the action link —
it is a live credential.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_UNCONFIGURED_WARNING = (
    "Invite saved, but no signup email can be sent until "
    "SUPABASE_SERVICE_ROLE_KEY is configured. If they already have an "
    "account, they'll get access at their next sign-in."
)
_FAILED_WARNING = (
    "Invite saved, but the signup link could not be created. If they already "
    "have an account, they'll get access at their next sign-in."
)


@dataclass
class InviteLinkResult:
    action_link: str | None
    already_registered: bool
    warning: str | None


def invites_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _is_email_exists(response: httpx.Response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    if not isinstance(body, dict):
        return False
    if body.get("error_code") == "email_exists":
        return True
    message = str(body.get("msg") or body.get("message") or "")
    return "already been registered" in message.lower()


async def generate_invite_link(email: str) -> InviteLinkResult:
    """Create the invitee's account and return their set-password link.

    Never raises: an existing account is reported via ``already_registered``,
    and any other failure degrades to a human-readable ``warning``.
    """
    if not invites_configured():
        return InviteLinkResult(None, False, _UNCONFIGURED_WARNING)

    payload: dict = {"type": "invite", "email": email}
    if settings.app_base_url:
        payload["redirect_to"] = settings.app_base_url
    key = settings.supabase_service_role_key
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/generate_link"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                json=payload,
            )
    except httpx.HTTPError:
        logger.warning("Supabase generate_link request failed", exc_info=True)
        return InviteLinkResult(None, False, _FAILED_WARNING)

    if response.is_success:
        try:
            action_link = response.json().get("action_link")
        except ValueError:
            action_link = None
        if action_link:
            return InviteLinkResult(action_link, False, None)
        logger.warning("Supabase generate_link returned no action_link")
        return InviteLinkResult(None, False, _FAILED_WARNING)

    if _is_email_exists(response):
        return InviteLinkResult(None, True, None)

    logger.warning("Supabase generate_link failed with status %s", response.status_code)
    return InviteLinkResult(None, False, _FAILED_WARNING)
