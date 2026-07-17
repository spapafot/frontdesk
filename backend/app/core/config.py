from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_REDACTED_SETTINGS = frozenset(
    {
        "deepseek_api_key",
        "openai_api_key",
        "jina_api_key",
        "database_url",
        "widget_session_secret",
        "edge_shared_secret",
        "supabase_jwt_secret",
        "supabase_service_role_key",
        "ingestion_queue_url",
        "stripe_secret_key",
        "stripe_webhook_secret",
    }
)


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
    # Optional on-demand LLM summaries for conversation history. Disabled by
    # default because the stored transcripts are usually short and already
    # readable, making the extra model call mostly latency and cost.
    conversation_summaries_enabled: bool = False

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
    rag_top_k: int = 12
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Follow-up query contextualization: rewrite an ambiguous latest message into
    # one standalone retrieval query using bounded recent conversation history.
    # The literal message is searched too, and any rewrite failure falls back to it.
    rag_query_contextualization: bool = True
    rag_query_context_messages: int = 6
    rag_query_context_chars: int = 6000
    rag_query_context_timeout: float = 6.0

    # Reranking (Jina): retrieve a wider candidate set, then have a cross-encoder
    # reorder it against the standalone question and keep the best `rag_top_k`.
    # Best-effort - skipped without `jina_api_key`, and any error/timeout falls
    # back to retrieval (cosine-score) order, so it never blocks an answer.
    # Candidates are truncated to `rag_rerank_snippet_chars` before sending, which
    # is enough signal to rank on and keeps Jina's per-token cost/latency low.
    rag_reranker: bool = True
    jina_api_key: str = ""
    jina_reranker_model: str = "jina-reranker-v2-base-multilingual"
    rag_rerank_candidates: int = 24
    rag_rerank_snippet_chars: int = 400
    rag_rerank_timeout: float = 6.0

    # Jina Reader (r.jina.ai): fetch a web page so a URL can be added to the
    # knowledge base. Reuses `jina_api_key`. The timeout is generous because
    # Reader renders JS-heavy pages server-side before returning.
    jina_reader_timeout: float = 30.0
    # Content extraction, tuned to cut boilerplate before chunking/embedding:
    #  * `text` returns clean plaintext and drops the link URLs that otherwise
    #    dominate nav-heavy pages (markdown keeps every `[label](long-url)`).
    #  * remove-selector strips common site chrome (menus, header/footer, forms)
    #    so mostly the main content is stored. Comma-separated; empty disables.
    #  * target-selector, if set, restricts extraction to one CSS selector
    #    (site-specific; usually left empty to read the whole cleaned page).
    jina_reader_format: str = "text"
    jina_reader_remove_selector: str = "nav,header,footer,aside,form"
    jina_reader_target_selector: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/support"
    # Force pgBouncer-safe connection args (no prepared-statement caching,
    # NullPool). Auto-enabled when the URL uses Supabase's 6543 pooler port.
    db_pgbouncer: bool = False

    # Asynchronous document ingestion (AWS S3 + SQS).
    aws_region: str = "eu-central-1"
    ingestion_bucket: str = ""
    ingestion_queue_url: str = ""

    # CORS
    frontend_origin: str = "http://localhost:5173"
    # Comma-separated list of customer domains allowed to embed the widget and
    # call the public chat API cross-origin. Use "*" to allow any origin (the
    # site key still authorizes the tenant). Example:
    #   WIDGET_ALLOWED_ORIGINS=https://acme.com,https://shop.acme.com
    widget_allowed_origins: str = ""
    widget_session_secret: str = ""
    widget_session_ttl_seconds: int = 900
    live_human_escalation_enabled: bool = False
    live_conversation_token_ttl_seconds: int = 14400
    live_socket_ticket_ttl_seconds: int = 60
    live_accept_timeout_seconds: int = 60
    # Visitor abuse moderation (OpenAI Moderation API; reuses openai_api_key).
    # Fail-open: errors/timeouts/missing key never block a normal answer.
    moderation_enabled: bool = True
    moderation_model: str = "omni-moderation-latest"
    moderation_timeout: float = 5.0
    moderation_strike_limit: int = 3

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
    # Require the edge proxy to attest that Turnstile passed before issuing a
    # public widget session. Enable only after the validating Worker is live.
    turnstile_required: bool = False
    turnstile_verified_header: str = "x-turnstile-verified"

    # Supabase Auth. Admin routes require a valid Supabase-issued JWT. Two
    # signing schemes are supported (auto-selected per token, see auth.py):
    #   * Legacy shared HS256 secret -> set ``supabase_jwt_secret``.
    #   * New asymmetric signing keys (ES256/RS256) -> set ``supabase_url``;
    #     the backend fetches the project's public JWKS to verify.
    # Newer Supabase projects have migrated to asymmetric keys, so setting
    # ``supabase_url`` is the current path; the secret is a fallback for
    # legacy/local setups. Leaving both empty disables admin auth (dev only).
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # Supabase signs user tokens with audience "authenticated".
    supabase_jwt_audience: str = "authenticated"
    # Cache lifetime for the fetched JWKS (seconds). Signing keys rotate rarely.
    supabase_jwks_cache_seconds: int = 600
    # Service-role key for the Supabase Admin API - used to create invited team
    # members' accounts, generate password-recovery links (generate_link), and
    # look up a user's MFA factors for aal2 enforcement. Empty disables all
    # three; invites still work for people who already have an account.
    supabase_service_role_key: str = ""
    # Require an aal2 (MFA-verified) token on admin routes for users who have a
    # verified MFA factor. The factor lookup uses the Supabase Admin API
    # (supabase_service_role_key); an unset key/url or a lookup error fails
    # OPEN - same philosophy as moderation - so an auxiliary outage never locks
    # the dashboard out. This flag is the operator kill-switch.
    mfa_enforcement_enabled: bool = True
    # Cache lifetime for a user's has-verified-factor answer (seconds).
    supabase_mfa_cache_seconds: int = 300
    # Public URL of the admin app; used as the redirect target for invite links
    # (must be in Supabase Auth's Redirect URLs allow-list). Empty falls back to
    # the Supabase project's configured Site URL. Also the base for Stripe
    # Checkout success/cancel and billing-portal return URLs.
    app_base_url: str = ""

    # --- Stripe billing (all optional; empty = billing disabled, so local dev
    # and self-hosting run without payments) --------------------------------
    # Secret API key and webhook signing secret. Both redacted (see
    # _REDACTED_SETTINGS). Price ids are not secret and identify the plan/interval
    # a Checkout session subscribes to; keep them in sync with app.core.plans.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_month: str = ""
    stripe_price_starter_year: str = ""
    stripe_price_pro_month: str = ""
    stripe_price_pro_year: str = ""
    stripe_price_business_month: str = ""
    stripe_price_business_year: str = ""
    # One-time "1,000 messages" top-up pack (Phase 2).
    stripe_price_topup: str = ""

    @property
    def supabase_jwks_url(self) -> str:
        """Public JWKS endpoint for the project's asymmetric signing keys."""
        if not self.supabase_url:
            return ""
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    def __repr_args__(self):
        """Keep credentials out of tracebacks, pytest fixture dumps, and logs."""
        for name, value in super().__repr_args__():
            yield name, "**********" if name in _REDACTED_SETTINGS and value else value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
