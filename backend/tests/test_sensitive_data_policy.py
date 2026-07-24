import logging

import pytest

from app.services.sensitive_data_policy import (
    BLOCK_CODE,
    BLOCK_MESSAGES,
    POLICY_VERSION,
    SensitiveDataPolicy,
    blocked_input_event,
    record_policy_decision,
)


def _synthetic(*parts: str) -> str:
    """Build detector fixtures without committing secret-shaped literals."""
    return "".join(parts)


@pytest.fixture
def policy():
    return SensitiveDataPolicy()


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nnot-real-key-data",
            "pem_private_key",
        ),
        (
            _synthetic("s", "k", "-proj-", "abcdefghijklmnopqrstuvwxyz123456"),
            "openai_api_token",
        ),
        (
            _synthetic("g", "hp_", "abcdefghijklmnopqrstuvwxyz123456"),
            "github_token",
        ),
        (
            _synthetic("g", "lpat-", "abcdefghijklmnopqrstuvwxyz1234"),
            "gitlab_token",
        ),
        (_synthetic("A", "KIA", "IOSFODNN7EXAMPLE"), "aws_access_key"),
        (
            _synthetic("s", "k", "_live_", "abcdefghijklmnopqrstuvwxyz"),
            "stripe_secret_key",
        ),
        (
            _synthetic("x", "oxb-", "123456789012-", "abcdefghijklmnop"),
            "slack_token",
        ),
        (
            _synthetic("A", "Iza", "SyD-", "abcdefghijklmnopqrstuvwxyz123456"),
            "google_api_key",
        ),
        (
            _synthetic(
                "S",
                "G.",
                "abcdefghijklmnop.",
                "abcdefghijklmnopqrstuvwxyz123456",
            ),
            "sendgrid_api_key",
        ),
        (
            _synthetic("n", "pm_", "abcdefghijklmnopqrstuvwxyz1234567890"),
            "npm_access_token",
        ),
        (
            _synthetic("h", "f_", "abcdefghijklmnopqrstuvwxyz1234"),
            "huggingface_token",
        ),
        (
            _synthetic("S", "K", "0123456789abcdef", "0123456789abcdef"),
            "twilio_api_key",
        ),
        (
            _synthetic("s", "hpat_", "0123456789abcdef", "0123456789abcdef"),
            "shopify_token",
        ),
        (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123",
            "jwt",
        ),
        ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz", "authorization_header"),
        ("postgresql://admin:supersafe@db.example/app", "credential_url"),
        ("password=hunter2", "credential_assignment"),
        ("password: letmein", "credential_assignment"),
        ("passcode=908172", "credential_assignment"),
        ("secret: correcthorse", "credential_assignment"),
        ("access_token=abcdefghijklmnopqrstuvwxyz", "credential_assignment"),
        ("client_secret: abcdefghijklmnop", "credential_assignment"),
        ("verification code: 123456", "verification_code_assignment"),
        ("otp=123-456", "verification_code_assignment"),
    ],
)
def test_blocks_supported_credential_formats(policy, text, rule_id):
    decision = policy.evaluate(text)

    assert decision.action == "block"
    assert "credential" in decision.categories
    assert rule_id in decision.rule_ids
    assert decision.policy_version == POLICY_VERSION


@pytest.mark.parametrize(
    "text",
    [
        "pass\u200bword＝hunter2",
        "Authorization\u200b： Bearer abcdefghijklmnopqrstuvwxyz",
        "sk\u2011proj\u2011abcdefghijklmnopqrstuvwxyz123456",
        "verification\u200b code：１２３４５６",
    ],
)
def test_normalizes_unicode_and_zero_width_obfuscation(policy, text):
    assert policy.evaluate(text).blocked


@pytest.mark.parametrize(
    "text",
    [
        "4111111111111111",
        "5555 5555 5555 4444",
        "3782-822463-10005",
        "6011\u200b1111\u200b1111\u200b1117",
        "３５３０ １１１３ ３３３０ ００００",
    ],
)
def test_blocks_luhn_valid_card_numbers(policy, text):
    decision = policy.evaluate(text)

    assert decision.blocked
    assert decision.categories == ("card",)
    assert decision.rule_ids == ("luhn_card_number",)


@pytest.mark.parametrize(
    "text",
    [
        "Please explain how password reset works.",
        "Password: required for sign-in.",
        "Password: use at least twelve characters.",
        "Use token-based pagination in this API.",
        "550e8400-e29b-41d4-a716-446655440000",
        "order reference: 4111111111111111",
        "phone: +4111111111111111",
        "4111111111111112",
        "1234567890123456",
        "0000000000000000",
        "Our order 1234-5678-9012-3456 is delayed.",
        "The minimum password length is twelve characters.",
    ],
)
def test_allows_conservative_false_positive_cases(policy, text):
    assert policy.evaluate(text).action == "allow"


def test_block_event_uses_exact_english_and_greek_copy():
    assert blocked_input_event("password=hunter2") == {
        "type": "input_blocked",
        "code": BLOCK_CODE,
        "message": BLOCK_MESSAGES["en"],
    }
    assert blocked_input_event("Ο κωδικός μου: password=hunter2") == {
        "type": "input_blocked",
        "code": BLOCK_CODE,
        "message": BLOCK_MESSAGES["el"],
    }


def test_telemetry_is_content_free(policy, caplog):
    secret = "password=never-log-this-value"
    decision = policy.evaluate(secret)

    with caplog.at_level(logging.WARNING):
        record_policy_decision(decision, profile_id=7, installation_id=17)

    assert "profile_id=7" in caplog.text
    assert "installation_id=17" in caplog.text
    assert "category=credential" in caplog.text
    assert "rule_id=credential_assignment" in caplog.text
    assert f"policy_version={POLICY_VERSION}" in caplog.text
    assert secret not in caplog.text
    assert "never-log-this-value" not in caplog.text
