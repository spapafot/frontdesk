"""Validation tests for the widget-appearance fields on ``SettingsUpdate``.

These exercise only the Pydantic schema, so they need no database (see
conftest.py - the suite deliberately avoids a real Postgres).
"""

import pytest
from pydantic import ValidationError

from app.schemas.settings import SettingsUpdate


def test_accepts_valid_appearance():
    body = SettingsUpdate(
        accent_color="#ff8800",
        launcher_icon="sparkles",
        launcher_position="bottom-left",
        greeting="Hey there!",
        launcher_label="Chat with us",
        show_branding=False,
    )
    assert body.accent_color == "#ff8800"
    assert body.launcher_icon == "sparkles"
    assert body.launcher_position == "bottom-left"
    assert body.show_branding is False


def test_accepts_short_hex():
    assert SettingsUpdate(accent_color="#fff").accent_color == "#fff"


@pytest.mark.parametrize("bad", ["0284c7", "#12", "#xyzxyz", "blue", "#12345"])
def test_rejects_bad_hex(bad):
    with pytest.raises(ValidationError):
        SettingsUpdate(accent_color=bad)


def test_rejects_unknown_icon():
    with pytest.raises(ValidationError):
        SettingsUpdate(launcher_icon="rocket")


def test_rejects_bad_position():
    with pytest.raises(ValidationError):
        SettingsUpdate(launcher_position="top-left")


def test_rejects_overlong_greeting_and_label():
    with pytest.raises(ValidationError):
        SettingsUpdate(greeting="x" * 501)
    with pytest.raises(ValidationError):
        SettingsUpdate(launcher_label="y" * 61)


def test_appearance_all_optional():
    # An update touching only non-appearance fields must not require them.
    body = SettingsUpdate(business_name="Acme")
    assert "accent_color" not in body.model_fields_set
    assert body.launcher_icon is None


def test_moderation_toggle_is_optional_and_defaults_off_the_wire():
    # Absent = leave unchanged (update_settings skips None fields).
    body = SettingsUpdate(business_name="Acme")
    assert body.moderation_enabled is None
    assert "moderation_enabled" not in body.model_fields_set
    assert SettingsUpdate(moderation_enabled=False).moderation_enabled is False


def test_notification_email_accepted_and_stripped():
    body = SettingsUpdate(notification_email="  owner@acme.com  ")
    assert body.notification_email == "owner@acme.com"


@pytest.mark.parametrize("bad", ["", "   ", "not-an-email", "a @b.com", "x@" + "y" * 260])
def test_notification_email_rejects_invalid_values(bad):
    # An empty value is invalid too: clearing the address (and silently killing
    # ticket notifications) is deliberately impossible.
    with pytest.raises(ValidationError):
        SettingsUpdate(notification_email=bad)


def test_notification_email_optional():
    body = SettingsUpdate(business_name="Acme")
    assert body.notification_email is None
    assert "notification_email" not in body.model_fields_set
