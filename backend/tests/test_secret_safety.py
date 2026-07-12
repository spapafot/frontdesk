from app.core.config import Settings, settings


def test_test_process_does_not_load_real_secrets():
    assert settings.deepseek_api_key == ""
    assert settings.openai_api_key == ""
    assert settings.widget_session_secret == ""
    assert settings.edge_shared_secret == ""
    assert settings.supabase_jwt_secret == ""
    assert settings.database_url == (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/support"
    )


def test_settings_repr_redacts_every_sensitive_value():
    secrets = {
        "deepseek_api_key": "deepseek-sentinel-secret",
        "openai_api_key": "openai-sentinel-secret",
        "database_url": "postgresql+asyncpg://user:sentinel-password@db.example/app",
        "widget_session_secret": "widget-sentinel-secret",
        "edge_shared_secret": "edge-sentinel-secret",
        "supabase_jwt_secret": "supabase-sentinel-secret",
    }
    rendered = repr(Settings(_env_file=None, **secrets))

    assert "**********" in rendered
    for secret in secrets.values():
        assert secret not in rendered
