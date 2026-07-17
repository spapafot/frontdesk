"""Self-service password recovery (public, rate-limited at the edge).

The response always has the same status and shape whether or not the account
exists: the one-time reset link travels only inside the ``recovery_notify``
payload, which the Cloudflare Worker strips before the response reaches any
browser and turns into an email (mirror of the team-invite boundary in
``deploy/cloudflare/worker/src/index.ts``). The endpoint is deliberately NOT
in ``_EDGE_EXEMPT_PATHS``, so the raw Lambda URL can neither farm recovery
links nor bypass the Worker's per-IP rate limit.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.auth import (
    PasswordRecoveryOut,
    PasswordRecoveryRequest,
    RecoveryNotify,
)
from app.services import supabase_admin

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_DETAIL = "If an account exists for this email, a reset link has been sent."


@router.post("/password-recovery", response_model=PasswordRecoveryOut)
async def request_password_recovery(
    body: PasswordRecoveryRequest,
) -> PasswordRecoveryOut:
    email = body.email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")

    action_link = await supabase_admin.generate_recovery_link(email)
    return PasswordRecoveryOut(
        detail=_GENERIC_DETAIL,
        recovery_notify=RecoveryNotify(email=email, action_link=action_link),
    )
