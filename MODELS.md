# Models

This document lists every model the AI Assistant uses, what we run **now** (local
development / prototype) and what we recommend for **production**, with the reasons
and the migration cost of switching.

All model identifiers live in [`backend/app/core/config.py`](backend/app/core/config.py)
and are overridable via environment variables (`.env`), so most swaps are config-only.

---

## Summary

| Role | Now (dev / prototype) | Production (recommended) |
| --- | --- | --- |
| Chat / reasoning (the "brain") | DeepSeek `deepseek-v4-flash` (thinking off) | DeepSeek `deepseek-v4-flash`, with a stronger fallback tier for hard queries |
| Speech-to-text (STT) | OpenAI `gpt-4o-mini-transcribe` | OpenAI `gpt-4o-transcribe` (or `gpt-4o-mini-transcribe` for cost) |
| Text-to-speech (TTS) | OpenAI `gpt-4o-mini-tts` (voice `alloy`) | OpenAI `gpt-4o-mini-tts`, per-business voice |
| Embeddings (RAG) | `intfloat/multilingual-e5-small` (local, 384-dim) | `BAAI/bge-m3` (1024-dim) or OpenAI `text-embedding-3-large` |
| Real-time voice (future) | None (turn-based STT -> LLM -> TTS over WebSocket) | OpenAI Realtime (`gpt-realtime`) for full-duplex, if/when needed |

---

## 1. Chat / reasoning model (the "brain")

- **Now:** `deepseek-v4-flash` via DeepSeek's OpenAI-compatible API
  (`base_url = https://api.deepseek.com`). Thinking mode is **disabled**
  (`deepseek_thinking = False`) because answers are grounded in retrieved
  knowledge-base context (RAG-always), so we want low latency and clean streaming
  rather than chain-of-thought.
- **Why:** cheap, fast time-to-first-token, OpenAI-compatible (so the same client
  code drives chat and the voice path), good multilingual handling.
- **Production:** keep `deepseek-v4-flash` as the default. Optionally add a
  **fallback tier** (a larger DeepSeek/other model) for long or low-confidence
  answers. The whole pipeline is OpenAI-compatible, so this is a config + routing
  change, not a rewrite.
- **Used by:** text chat (`/chat/stream`) and voice (`/voice/ws`) share the same
  core, `chat_service.run_turn(...)`.

## 2. Speech-to-text (STT)

- **Now:** OpenAI `gpt-4o-mini-transcribe`.
- **Why:** we moved off `whisper-1` because it mis-detected accented English as
  the wrong language/script; `gpt-4o-mini-transcribe` detects language far more
  reliably and is inexpensive.
- **Production:** `gpt-4o-transcribe` (full) gives the best accuracy for noisy
  phone-grade audio; keep `gpt-4o-mini-transcribe` if cost matters more than the
  last few points of accuracy.
- **Used by:** the mic button in text chat and the voice WebSocket
  (`speech_service.transcribe`).

## 3. Text-to-speech (TTS)

- **Now:** OpenAI `gpt-4o-mini-tts`, default voice `alloy`.
- **Configurable per business:** `tts_voice` and `tts_speed` (see the `businesses`
  table / settings). Playback speed is applied client-side.
- **Why:** natural-sounding, low latency, large voice selection; per-sentence
  synthesis lets audio start playing while the reply is still streaming.
- **Production:** same model is production-grade. Choose a default voice per brand
  and expose the picker in settings (already supported).
- **Used by:** `speech_service.synthesize`, the chat `SpeechQueue`, and the voice
  `AudioFrameQueue`.

## 4. Embeddings (RAG retrieval)

- **Now:** `intfloat/multilingual-e5-small`, run **locally** via
  `sentence-transformers`. 384 dimensions. Requires `query:` / `passage:` prefixes
  (already handled in `embeddings.py`).
- **Why:** retrieval-tuned and multilingual, so Greek queries match English
  documents reliably; runs in-process with no extra API cost; 384-dim matches the
  current `pgvector` column so no schema change was needed.
- **Production candidates:**
  - **`BAAI/bge-m3`** (1024-dim) — stronger multilingual retrieval, still
    self-hostable. **Migration cost:** change `embedding_dim` to 1024, run an
    Alembic migration to alter the `knowledge_chunks.embedding` vector column, and
    **re-index all documents** (re-chunk + re-embed).
  - **OpenAI `text-embedding-3-large`** (3072-dim) or `-small` (1536-dim) — top
    quality, no GPU to manage, but adds per-embedding API cost and a network hop on
    every query and ingest. Same migration cost (dim change + full re-index).
- **Important:** any embedding-model change that alters dimensions requires a
  vector-column migration **and** a full re-index, because old and new vectors are
  not comparable. Use the existing re-index helpers
  (`reindex_embeddings.py` / `reingest_documents.py`).

## 5. Vector search index

- **Now / Production:** Postgres + `pgvector` with an **HNSW** index on
  `knowledge_chunks.embedding` using `vector_cosine_ops` (migration
  `0009_knowledge_chunk_hnsw_index`). This matches the cosine ordering used by the
  search query and scales as the knowledge base grows.

## 6. Real-time voice (future / optional)

- **Now:** voice is **turn-based** (push-to-talk): browser streams mic audio over
  `/voice/ws` -> STT -> DeepSeek + RAG -> per-sentence TTS -> audio streamed back.
  The brain stays DeepSeek so all guardrails and RAG behavior are reused.
- **Production (only if full-duplex is needed):** OpenAI Realtime
  (`gpt-realtime`) enables barge-in and the lowest latency speech-to-speech, with
  the knowledge base exposed as a tool/function call. Trade-offs: the conversational
  brain becomes OpenAI's realtime model (diverging from DeepSeek), guardrails must be
  ported to the Realtime session config, and audio tokens cost more. Not needed for
  the current turn-based experience.

---

## Where to change models

Edit `.env` (preferred) or the defaults in
[`backend/app/core/config.py`](backend/app/core/config.py):

| Setting | Controls |
| --- | --- |
| `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_THINKING` | Chat brain |
| `OPENAI_STT_MODEL` | Speech-to-text |
| `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE` | Text-to-speech (voice also per-business) |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `EMBEDDING_QUERY_PREFIX`, `EMBEDDING_PASSAGE_PREFIX` | RAG embeddings (dim change => migration + re-index) |
