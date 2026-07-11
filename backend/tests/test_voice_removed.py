from app.main import app
from app.schemas.chat import ChatRequest
from app.schemas.settings import SettingsOut, SettingsUpdate


def test_voice_routes_are_not_registered():
    paths = {route.path for route in app.routes}
    assert "/speech/transcribe" not in paths
    assert "/speech/tts" not in paths
    assert "/voice/ws" not in paths


def test_public_schemas_do_not_expose_voice_fields():
    assert "voice" not in ChatRequest.model_fields
    assert "tts_voice" not in SettingsOut.model_fields
    assert "tts_speed" not in SettingsOut.model_fields
    assert "tts_voice" not in SettingsUpdate.model_fields
    assert "tts_speed" not in SettingsUpdate.model_fields
