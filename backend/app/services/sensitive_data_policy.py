"""Deterministic high-confidence blocking for secrets and payment-card data.

The policy deliberately returns content-free metadata. Callers must never log
the input, the matching value, or surrounding text.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

POLICY_VERSION = "2026-07-24.1"
BLOCK_CODE = "sensitive_data_detected"
BLOCK_MESSAGES = {
    "en": (
        "This message appears to contain a password, security key, verification "
        "code, or payment-card number. For your safety, it was not sent or saved. "
        "Remove that information and try again."
    ),
    "el": (
        "Αυτό το μήνυμα φαίνεται να περιέχει κωδικό πρόσβασης, κλειδί ασφαλείας, "
        "κωδικό επαλήθευσης ή αριθμό κάρτας πληρωμής. Για την ασφάλειά σας, δεν "
        "στάλθηκε ούτε αποθηκεύτηκε. Αφαιρέστε αυτές τις πληροφορίες και δοκιμάστε ξανά."
    ),
}

SensitiveCategory = Literal["credential", "card"]
PolicyAction = Literal["allow", "block"]


@dataclass(frozen=True)
class SensitiveDataDecision:
    action: PolicyAction
    categories: tuple[SensitiveCategory, ...] = ()
    rule_ids: tuple[str, ...] = ()
    policy_version: str = POLICY_VERSION

    @property
    def blocked(self) -> bool:
        return self.action == "block"


_GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_DASHES = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\ufe58": "-",
        "\ufe63": "-",
    }
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).translate(_DASHES)
    # Format controls include the common zero-width joiners/non-joiners and
    # directional marks used to split otherwise detectable credentials.
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    return re.sub(r"[\t\v\f\r ]+", " ", normalized)


_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "pem_private_key",
        re.compile(
            r"-----BEGIN\s+(?:(?:RSA|EC|DSA|OPENSSH|ENCRYPTED)\s+)?PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        "authorization_header",
        re.compile(
            r"\bauthorization\s*[:=]\s*(?:bearer|basic|token)\s+"
            r"[A-Za-z0-9._~+/=-]{8,}",
            re.IGNORECASE,
        ),
    ),
    (
        "jwt",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\."
            r"[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}(?![A-Za-z0-9_-])"
        ),
    ),
    (
        "openai_api_token",
        re.compile(r"\bsk-(?:(?:proj|svcacct)-)?[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "github_token",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
        ),
    ),
    (
        "gitlab_token",
        re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "aws_access_key",
        re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    ),
    (
        "stripe_secret_key",
        re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    ),
    (
        "sendgrid_api_key",
        re.compile(r"\bSG\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "npm_access_token",
        re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b"),
    ),
    (
        "huggingface_token",
        re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "twilio_api_key",
        re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
    ),
    (
        "shopify_token",
        re.compile(r"\bshp(?:at|ca|pa|ss)_[A-Fa-f0-9]{32}\b"),
    ),
    (
        "credential_url",
        re.compile(
            r"\b(?:https?|ftp|postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|"
            r"redis|rediss|amqp|amqps)://"
            r"[^/\s:@]+:[^@/\s]+@",
            re.IGNORECASE,
        ),
    ),
)

_ASSIGNMENT_RE = re.compile(
    r"\b(?P<label>"
    r"password|passwd|pwd|passcode|"
    r"(?:api[\s_-]*)?secret|api[\s_-]*key|"
    r"(?:access|refresh|auth|session)[\s_-]*token|token|"
    r"client[\s_-]*secret|private[\s_-]*key"
    r")\s*(?:=|:)\s*"
    r"(?P<value>\"[^\"\r\n]{4,256}\"|'[^'\r\n]{4,256}'|[^\s,;]{4,256})",
    re.IGNORECASE,
)

_VERIFICATION_CODE_RE = re.compile(
    r"\b(?:verification|security|one[\s_-]*time|2fa|mfa|otp)"
    r"(?:[\s_-]*(?:code|pin))?\s*(?:=|:)\s*"
    r"(?P<code>\d(?:[\s-]*\d){3,9})\b",
    re.IGNORECASE,
)

_PLACEHOLDER_VALUES = {
    "changed",
    "example",
    "hidden",
    "minimum",
    "must",
    "needs",
    "optional",
    "password",
    "placeholder",
    "redacted",
    "reset",
    "required",
    "secret",
    "should",
    "unknown",
    "use",
}

_CARD_CANDIDATE_RE = re.compile(
    r"(?<!\d)(?:\d[\s.\-\u00b7\u2022]*){12,18}\d(?!\d)"
)
_NON_CARD_CONTEXT_RE = re.compile(
    r"\b(?:account|invoice|order|phone|telephone|mobile|fax|reference|ref|"
    r"tracking)(?:\s+(?:number|no|id))?\s*[:#=-]?\s*$",
    re.IGNORECASE,
)


def _is_high_confidence_assignment(match: re.Match[str]) -> bool:
    value = match.group("value")
    if value[:1] in {'"', "'"}:
        return True
    cleaned = value.strip().lower()
    if cleaned in _PLACEHOLDER_VALUES or cleaned.startswith(("<", "{", "[")):
        return False
    return True


def _luhn_valid(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        value = int(character)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _contains_card(text: str) -> bool:
    for match in _CARD_CANDIDATE_RE.finditer(text):
        digits = "".join(character for character in match.group() if character.isdigit())
        if not 13 <= len(digits) <= 19:
            continue
        if len(set(digits)) == 1 or not _luhn_valid(digits):
            continue
        prefix = text[max(0, match.start() - 40) : match.start()]
        # A leading plus or an explicit phone/order/reference label is a strong
        # signal that a Luhn-valid coincidence is not a payment card.
        if prefix.rstrip().endswith("+") or _NON_CARD_CONTEXT_RE.search(prefix):
            continue
        return True
    return False


class SensitiveDataPolicy:
    """Evaluate new AI input without retaining or returning its content."""

    def evaluate(self, text: str) -> SensitiveDataDecision:
        normalized = _normalize(text)
        rule_ids: list[str] = []
        categories: list[SensitiveCategory] = []

        for rule_id, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(normalized):
                rule_ids.append(rule_id)
                if "credential" not in categories:
                    categories.append("credential")

        if any(
            _is_high_confidence_assignment(match)
            for match in _ASSIGNMENT_RE.finditer(normalized)
        ):
            rule_ids.append("credential_assignment")
            if "credential" not in categories:
                categories.append("credential")

        if _VERIFICATION_CODE_RE.search(normalized):
            rule_ids.append("verification_code_assignment")
            if "credential" not in categories:
                categories.append("credential")

        if _contains_card(normalized):
            rule_ids.append("luhn_card_number")
            categories.append("card")

        if not rule_ids:
            return SensitiveDataDecision(action="allow")
        return SensitiveDataDecision(
            action="block",
            categories=tuple(categories),
            rule_ids=tuple(dict.fromkeys(rule_ids)),
        )


sensitive_data_policy = SensitiveDataPolicy()


def blocked_input_event(message: str) -> dict[str, str]:
    language = "el" if _GREEK_RE.search(message) else "en"
    return {
        "type": "input_blocked",
        "code": BLOCK_CODE,
        "message": BLOCK_MESSAGES[language],
    }


def record_policy_decision(
    decision: SensitiveDataDecision,
    *,
    profile_id: int,
    installation_id: int | None,
) -> None:
    """Emit content-free telemetry for blocked turns only."""
    for rule_id in decision.rule_ids:
        category = "card" if rule_id == "luhn_card_number" else "credential"
        logger.warning(
            (
                "Sensitive input blocked profile_id=%s installation_id=%s "
                "category=%s rule_id=%s action=%s policy_version=%s"
            ),
            profile_id,
            installation_id,
            category,
            rule_id,
            decision.action,
            decision.policy_version,
        )
