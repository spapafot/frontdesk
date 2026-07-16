from types import SimpleNamespace

from app.services import moderation
from app.services.moderation import ModerationVerdict


def _fake_response(categories: dict) -> SimpleNamespace:
    fake_categories = SimpleNamespace(model_dump=lambda by_alias=False: categories)
    return SimpleNamespace(results=[SimpleNamespace(categories=fake_categories)])


async def test_classify_skipped_without_key(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "")

    async def _no_request(_text):
        raise AssertionError("classify must not call the API without a key")

    monkeypatch.setattr(moderation, "_request", _no_request)

    assert await moderation.classify("abusive text") is None


async def test_classify_skipped_when_disabled(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", False)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _no_request(_text):
        raise AssertionError("classify must not run when disabled")

    monkeypatch.setattr(moderation, "_request", _no_request)

    assert await moderation.classify("abusive text") is None


async def test_classify_skipped_for_blank_input(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _no_request(_text):
        raise AssertionError("classify must not run on blank input")

    monkeypatch.setattr(moderation, "_request", _no_request)

    assert await moderation.classify("   \n") is None


async def test_classify_fails_open_on_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _request(_text):
        raise RuntimeError("moderation API unavailable")

    monkeypatch.setattr(moderation, "_request", _request)

    assert await moderation.classify("abusive text") is None


async def test_classify_extracts_strike_categories_sorted(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _request(_text):
        return _fake_response(
            {
                "harassment/threatening": True,
                "harassment": True,
                "hate": False,
                "self-harm": False,
            }
        )

    monkeypatch.setattr(moderation, "_request", _request)

    verdict = await moderation.classify("abusive text")

    assert verdict == ModerationVerdict(
        flagged=True, categories=("harassment", "harassment/threatening")
    )


async def test_classify_never_strikes_self_harm(monkeypatch, settings):
    # A visitor in distress must not be warned or locked out.
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _request(_text):
        return _fake_response(
            {
                "self-harm": True,
                "self-harm/intent": True,
                "self-harm/instructions": True,
                "harassment": False,
            }
        )

    monkeypatch.setattr(moderation, "_request", _request)

    verdict = await moderation.classify("message")

    assert verdict == ModerationVerdict(flagged=False, categories=())


async def test_classify_ignores_unknown_categories(monkeypatch, settings):
    monkeypatch.setattr(settings, "moderation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def _request(_text):
        return _fake_response({"illicit": True, "violence": True, "hate": True})

    monkeypatch.setattr(moderation, "_request", _request)

    verdict = await moderation.classify("message")

    assert verdict == ModerationVerdict(flagged=True, categories=("hate",))
