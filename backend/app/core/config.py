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

    # OpenAI (speech + embeddings). Uses the real OpenAI API, separate from the
    # DeepSeek-compatible chat client above.
    openai_api_key: str = ""
    # gpt-4o-mini-transcribe detects language far more reliably than whisper-1
    # (avoids transcribing accented English into the wrong script).
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"

    # Embeddings. API-based OpenAI model (no local PyTorch), so the backend stays
    # small enough for serverless/Lambda. text-embedding-3-small is multilingual
    # and returns 1536-dim vectors. Changing this requires a pgvector column
    # migration + a full re-index of existing documents.
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Retrieval / chunking. Kept modest so the injected context stays small and
    # the model's time-to-first-token stays low.
    rag_top_k: int = 8
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Voice replies must come back fast, so they use a much leaner context:
    # fewer chunks, a shorter slice of history, and a "speak concisely" directive.
    voice_rag_top_k: int = 5
    voice_history_messages: int = 6

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/support"
    )

    # CORS
    frontend_origin: str = "http://localhost:5173"
    # Comma-separated list of customer domains allowed to embed the widget and
    # call the public chat API cross-origin. Use "*" to allow any origin (the
    # site key still authorizes the tenant). Example:
    #   WIDGET_ALLOWED_ORIGINS=https://acme.com,https://shop.acme.com
    widget_allowed_origins: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        origins = [self.frontend_origin]
        extra = [o.strip() for o in self.widget_allowed_origins.split(",") if o.strip()]
        origins.extend(extra)
        return origins

    # Tool loop safety
    max_tool_iterations: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
