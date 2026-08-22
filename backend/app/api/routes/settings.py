from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_selected_site, require_site_owner
from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.core.config import settings
from app.core.origins import normalize_origin
from app.models.profile import AssistantProfile
from app.repositories.commerce_repository import WooCommerceCatalogRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.settings import (
    SettingsOut,
    SettingsUpdate,
    WooCommerceVerifyOut,
    WooCommerceVerifyRequest,
)
from app.services import billing
from app.services.woocommerce import (
    WooCommerceError,
    WooCommerceStoreClient,
    normalize_store_url,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _month() -> tuple[date, str]:
    now = datetime.now(timezone.utc)
    period = date(now.year, now.month, 1)
    if now.month == 12:
        reset = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        reset = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return period, reset.isoformat()


async def _to_out(profile: AssistantProfile, session: AsyncSession) -> SettingsOut:
    repo = WidgetRepository(session)
    installation = await repo.get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    period, reset = _month()
    catalog = await WooCommerceCatalogRepository(session).get(profile.id)
    return SettingsOut(
        business_name=profile.name,
        assistant_name=profile.assistant_name,
        custom_instructions=profile.custom_instructions,
        public_key=installation.public_key,
        widget_origin=installation.allowed_origin,
        widget_enabled=installation.is_enabled,
        widget_monthly_usage=await repo.usage(installation.id, period),
        widget_resets_at=reset,
        accent_color=installation.accent_color,
        launcher_icon=installation.launcher_icon,
        launcher_position=installation.launcher_position,
        greeting=installation.greeting,
        launcher_label=installation.launcher_label,
        show_branding=installation.show_branding,
        live_human_escalation_enabled=profile.live_human_escalation_enabled,
        live_human_escalation_available=settings.live_human_escalation_enabled,
        moderation_enabled=profile.moderation_enabled,
        moderation_available=settings.moderation_enabled
        and bool(settings.openai_api_key),
        notification_email=profile.notification_email,
        talk_to_person_after=profile.talk_to_person_after,
        woocommerce_store_url=catalog.store_url if catalog else None,
        woocommerce_catalog_enabled=catalog.enabled if catalog else False,
        woocommerce_catalog_verified_at=catalog.verified_at if catalog else None,
    )


async def _verify_catalog(store_url: str) -> tuple[str, dict, datetime]:
    try:
        normalized = normalize_store_url(store_url)
        metadata = await WooCommerceStoreClient(normalized).verify_and_discover()
    except WooCommerceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return normalized, metadata, datetime.now(timezone.utc)


@router.get("", response_model=SettingsOut)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_selected_site),
) -> SettingsOut:
    return await _to_out(profile, session)


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    # Reads are team-readable (the app shell needs them); writes are owner-only.
    profile: AssistantProfile = Depends(require_site_owner),
    user: AdminUser = Depends(require_admin),
) -> SettingsOut:
    # Plan-gated feature writes: enabling live handoff or removing branding both
    # require the entitlement. Turning either back off is always allowed.
    if body.live_human_escalation_enabled is True or body.show_branding is False:
        entitlements = await billing.resolve_entitlements(
            session, user, profile.owner_user_id
        )
        if body.live_human_escalation_enabled is True and not entitlements.live_handoff:
            raise HTTPException(
                status_code=402,
                detail="Live human handoff is available on the Pro and Business plans. Upgrade to enable it.",
            )
        if body.show_branding is False and not entitlements.remove_branding:
            raise HTTPException(
                status_code=402,
                detail="Removing branding is available on the Pro and Business plans. Upgrade to hide it.",
            )
    await ProfileRepository(session).update_settings(
        profile,
        name=body.business_name,
        assistant_name=body.assistant_name,
        custom_instructions=body.custom_instructions,
        live_human_escalation_enabled=body.live_human_escalation_enabled,
        moderation_enabled=body.moderation_enabled,
        notification_email=body.notification_email,
        talk_to_person_after=body.talk_to_person_after,
    )
    installation = await WidgetRepository(session).get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    if "widget_origin" in body.model_fields_set:
        installation.allowed_origin = normalize_origin(body.widget_origin)
    if body.widget_enabled is not None:
        installation.is_enabled = body.widget_enabled
    if body.accent_color is not None:
        installation.accent_color = body.accent_color
    if body.launcher_icon is not None:
        installation.launcher_icon = body.launcher_icon
    if body.launcher_position is not None:
        installation.launcher_position = body.launcher_position
    if body.greeting is not None:
        installation.greeting = body.greeting
    if "launcher_label" in body.model_fields_set:
        installation.launcher_label = (body.launcher_label or "").strip() or None
    if body.show_branding is not None:
        installation.show_branding = body.show_branding

    catalog_repo = WooCommerceCatalogRepository(session)
    catalog = await catalog_repo.get(profile.id)
    url_supplied = "woocommerce_store_url" in body.model_fields_set
    enabled_supplied = "woocommerce_catalog_enabled" in body.model_fields_set
    if url_supplied or enabled_supplied:
        requested_url = (
            body.woocommerce_store_url
            if url_supplied
            else (catalog.store_url if catalog is not None else None)
        )
        requested_enabled = (
            bool(body.woocommerce_catalog_enabled)
            if enabled_supplied
            else (catalog.enabled if catalog is not None else False)
        )
        if not requested_url:
            if requested_enabled:
                raise HTTPException(
                    status_code=422,
                    detail="Connect a WooCommerce store before enabling product search.",
                )
            if catalog is not None:
                await catalog_repo.delete(catalog)
        else:
            try:
                normalized = normalize_store_url(requested_url)
            except WooCommerceError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            changed = catalog is None or catalog.store_url != normalized
            metadata = None
            verified_at = None
            enabling = requested_enabled and (catalog is None or not catalog.enabled)
            if changed or enabling:
                normalized, metadata, verified_at = await _verify_catalog(normalized)
            await catalog_repo.upsert(
                profile.id,
                store_url=normalized,
                enabled=requested_enabled,
                catalog_metadata=metadata,
                verified_at=verified_at,
            )
    await session.commit()
    return await _to_out(profile, session)


@router.post("/woocommerce/verify", response_model=WooCommerceVerifyOut)
async def verify_woocommerce_catalog(
    body: WooCommerceVerifyRequest,
    profile: AssistantProfile = Depends(require_site_owner),
) -> WooCommerceVerifyOut:
    """Verify a prospective public catalog without persisting it."""
    normalized, metadata, _ = await _verify_catalog(body.store_url)
    currency = metadata.get("currency") or {}
    return WooCommerceVerifyOut(
        store_url=normalized,
        product_count=int(metadata.get("product_count") or 0),
        currency_code=currency.get("code"),
        categories=len(metadata.get("categories") or []),
        attributes=len(metadata.get("attributes") or []),
    )


@router.post("/widget-key/rotate", response_model=SettingsOut)
async def rotate_widget_key(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(require_site_owner),
) -> SettingsOut:
    repo = WidgetRepository(session)
    installation = await repo.get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    await repo.rotate(installation)
    await session.commit()
    return await _to_out(profile, session)
