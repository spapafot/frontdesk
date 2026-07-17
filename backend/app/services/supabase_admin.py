"""Create invited users via the Supabase Admin API (service-role key).

Only ``generate_link`` is used: it creates the account and returns a one-time
set-password action link WITHOUT Supabase sending any email - delivery happens
at the edge via Cloudflare Email Sending (see the Worker's invite interception).

Best-effort by design: the membership row is the real access mechanism (it
activates by email match at the member's first login), so a failure here must
never fail the invite request. Nothing in this module may log the action link -
it is a live credential.
"""

import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

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
_REDIRECT_WARNING = (
    "Invite saved, but Supabase did not accept APP_BASE_URL as the invite "
    "redirect. Add it to Authentication > URL Configuration > Redirect URLs "
    "in Supabase, then invite this person again."
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


def _returned_redirect(body: dict, action_link: str) -> str | None:
    redirect = body.get("redirect_to")
    if isinstance(redirect, str) and redirect:
        return redirect
    values = parse_qs(urlsplit(action_link).query).get("redirect_to")
    return values[0] if values else None


def _same_redirect(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


async def generate_invite_link(email: str) -> InviteLinkResult:
    """Create the invitee's account and return their set-password link.

    Never raises: an existing account is reported via ``already_registered``,
    and any other failure degrades to a human-readable ``warning``.
    """
    if not invites_configured():
        return InviteLinkResult(None, False, _UNCONFIGURED_WARNING)

    payload: dict = {"type": "invite", "email": email}
    params = (
        {"redirect_to": settings.app_base_url} if settings.app_base_url else None
    )
    key = settings.supabase_service_role_key
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/generate_link"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                params=params,
                json=payload,
            )
    except httpx.HTTPError:
        logger.warning("Supabase generate_link request failed", exc_info=True)
        return InviteLinkResult(None, False, _FAILED_WARNING)

    if response.is_success:
        try:
            body = response.json()
        except ValueError:
            body = {}
        action_link = body.get("action_link")
        if action_link:
            returned_redirect = _returned_redirect(body, action_link)
            if (
                settings.app_base_url
                and returned_redirect
                and not _same_redirect(returned_redirect, settings.app_base_url)
            ):
                logger.warning(
                    "Supabase rejected the configured invite redirect URL"
                )
                return InviteLinkResult(None, False, _REDIRECT_WARNING)
            return InviteLinkResult(action_link, False, None)
        logger.warning("Supabase generate_link returned no action_link")
        return InviteLinkResult(None, False, _FAILED_WARNING)

    if _is_email_exists(response):
        return InviteLinkResult(None, True, None)

    logger.warning("Supabase generate_link failed with status %s", response.status_code)
    return InviteLinkResult(None, False, _FAILED_WARNING)
