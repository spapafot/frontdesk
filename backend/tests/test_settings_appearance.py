"""Validation tests for the widget-appearance fields on ``SettingsUpdate``.

These exercise only the Pydantic schema, so they need no database (see
conftest.py — the suite deliberately avoids a real Postgres).
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
