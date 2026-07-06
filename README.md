# AI Customer Support — Document Knowledge Base

A local chat assistant that answers customer questions using ONLY the documents you
upload. Uploaded files are parsed, chunked, embedded (pgvector), and retrieved at
question time. The assistant refuses or escalates when the answer is not in your
documents, and never reveals how it works.

- **Backend:** FastAPI, PostgreSQL + pgvector, SQLAlchemy 2.0 (async), Alembic,
  DeepSeek (streaming chat), OpenAI `text-embedding-3-small` embeddings (API-based).
- **Frontend:** Vite + React + TypeScript + Tailwind. A Chat view and a Knowledge base
  admin view for uploading and managing documents.

Supported upload formats: TXT, PDF, DOC, DOCX, XLS, XLSX (max 10 MB each).

## Prerequisites

- Docker (for Postgres + the backend)
- Node 18+ (for the frontend)
- A DeepSeek API key (chat) and an OpenAI API key (embeddings + voice)

## 1. Backend

```bash
cd backend
cp .env.example .env          # then set DEEPSEEK_API_KEY in .env

# start Postgres + the API
docker compose up -d --build

# create the schema
docker compose run --rm backend alembic upgrade head
```

The API is available at http://localhost:8000 (health check: `/health`). A single
default business is created automatically on first use — there is no seed data.

> Note: embeddings are API-based (OpenAI `text-embedding-3-small`, 1536-dim)
> all-MiniLM-L6-v2 is used oonly locally and is not downloaded in production
> Set `OPENAI_API_KEY` for retrieval and voice. See [MODELS.md](MODELS.md).

## 2. Frontend

```bash
cd frontend
cp .env.example .env          # VITE_API_BASE defaults to http://localhost:8000
npm install
npm run dev
```

Open http://localhost:5173.

## How to use

1. Open the **Knowledge base** tab and upload one or more documents.
2. Switch to the **Chat** tab and ask questions. The assistant answers only from the
   uploaded content and says it doesn't have the information otherwise.
3. Toggle **Debug** in the chat header to see the retrieved chunks behind each answer.

## Deployment (production)

The repo ships an infrastructure-as-scripts setup for a chat-only production
deployment on **`plugandplay.gr`**. Full runbook: [DEPLOY.md](DEPLOY.md).

| Component             | Role                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| **Supabase**          | Postgres + pgvector (database) and Supabase Auth                                                     |
| **AWS Lambda**        | FastAPI backend as a container image (ECR) behind a Function URL with `RESPONSE_STREAM` for SSE chat |
| **Cloudflare Worker** | Reverse proxy at `api.plugandplay.gr`; injects a shared secret and rate-limits chat                  |
| **Cloudflare Pages**  | Admin app (`app.plugandplay.gr`) + embeddable widget (`cdn.plugandplay.gr`)                          |

**Three security layers:** a Worker↔Lambda shared secret (blocks direct hits to
the raw Function URL), Supabase JWT auth on admin routes, and `site_key` + CORS +
rate-limiting on the public chat endpoint. Voice is disabled in this deployment
(Lambda Function URLs don't support WebSockets); it still runs in local dev.

## Testing

```bash
cd backend  && pytest         # API / auth tests (no DB required)
cd frontend && npm test       # component + integration tests (vitest)
```

CI runs both suites on every pull request to `main` (`.github/workflows/ci.yml`).

## Knowledge base API

- `POST /knowledge/documents` — multipart upload (`file`)
- `GET /knowledge/documents` — list documents with chunk counts
- `GET /knowledge/documents/{id}/chunks` — preview a document's chunks
- `PATCH /knowledge/documents/{id}` — enable/disable (`{"is_active": false}`)
- `DELETE /knowledge/documents/{id}` — delete a document and its chunks
