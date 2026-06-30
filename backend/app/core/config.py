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

    # OpenAI (speech-to-text + text-to-speech). Uses the real OpenAI API,
    # separate from the DeepSeek-compatible chat client above.
    openai_api_key: str = ""
    # gpt-4o-mini-transcribe detects language far more reliably than whisper-1
    # (avoids transcribing accented English into the wrong script).
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"

    # Embeddings. Retrieval-tuned multilingual model (384 dims, so no schema change)
    # for reliable cross-lingual ranking — e.g. Greek queries over English docs.
    # e5 models require "query:" / "passage:" prefixes. Changing this needs re-indexing.
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384
    embedding_query_prefix: str = "query: "
    embedding_passage_prefix: str = "passage: "

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

    # Tool loop safety
    max_tool_iterations: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
