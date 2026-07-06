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
- A DeepSeek API key

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

> Note: DeepSeek has no embeddings endpoint, so retrieval uses a local
> `all-MiniLM-L6-v2` model (384-dim). The first run downloads the model into the
> `models` Docker volume.

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

## Knowledge base API

- `POST /knowledge/documents` — multipart upload (`file`)
- `GET /knowledge/documents` — list documents with chunk counts
- `GET /knowledge/documents/{id}/chunks` — preview a document's chunks
- `PATCH /knowledge/documents/{id}` — enable/disable (`{"is_active": false}`)
- `DELETE /knowledge/documents/{id}` — delete a document and its chunks
