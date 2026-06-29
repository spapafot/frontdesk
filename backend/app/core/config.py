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

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Retrieval / chunking
    rag_top_k: int = 10
    chunk_size: int = 1200
    chunk_overlap: int = 200

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
