from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # DeepSeek (OpenAI-compatible)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    # V4-Flash defaults thinking ON; we keep it OFF since answers come straight
    # from the knowledge base (lower latency/cost, simpler streaming).
    deepseek_thinking: bool = False

    # OpenAI embeddings. Uses the real OpenAI API, separate from the
    # DeepSeek-compatible chat client above.
    openai_api_key: str = ""

    # Embeddings. API-based OpenAI model (no local PyTorch), so the backend stays
    # small enough for serverless/Lambda. text-embedding-3-large is multilingual
    # and defaults to 3072-dim vectors, but we request 1536 dims explicitly (via
    # the `dimensions` API param) to keep the pgvector column size unchanged.
    # Changing embedding_dim requires a pgvector column migration + a full
    # re-index of existing documents.
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 1536

    # Retrieval / chunking. Kept modest so the injected context stays small and
    # the model's time-to-first-token stays low.
    rag_top_k: int = 8
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/support"
    )
    # Force pgBouncer-safe connection args (no prepared-statement caching,
    # NullPool). Auto-enabled when the URL uses Supabase's 6543 pooler port.
    db_pgbouncer: bool = False

    # CORS
    frontend_origin: str = "http://localhost:5173"
    # Comma-separated list of customer domains allowed to embed the widget and
    # call the public chat API cross-origin. Use "*" to allow any origin (the
    # site key still authorizes the tenant). Example:
    #   WIDGET_ALLOWED_ORIGINS=https://acme.com,https://shop.acme.com
    widget_allowed_origins: str = ""
    widget_session_secret: str = ""
    widget_session_ttl_seconds: int = 900
    widget_monthly_limit: int = 5000

    @property
    def allowed_origins(self) -> list[str]:
        origins = [self.frontend_origin]
        extra = [o.strip() for o in self.widget_allowed_origins.split(",") if o.strip()]
        origins.extend(extra)
        return origins

    # --- Production auth (all optional; empty = disabled, so local dev is
    # unchanged) --------------------------------------------------------------
    # Shared secret injected by the edge proxy (Cloudflare Worker) on every
    # request and verified by EdgeSecretMiddleware. Blocks direct hits to the
    # raw Lambda Function URL. Empty string disables the check.
    edge_shared_secret: str = ""
    edge_secret_header: str = "x-edge-secret"

    # Supabase Auth. When ``supabase_jwt_secret`` is set, admin routes require a
    # valid Supabase-issued JWT (HS256). Empty disables admin auth (dev only).
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # Supabase signs user tokens with audience "authenticated".
    supabase_jwt_audience: str = "authenticated"

    @property
    def admin_auth_enabled(self) -> bool:
        return bool(self.supabase_jwt_secret)

    # Tool loop safety
    max_tool_iterations: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
