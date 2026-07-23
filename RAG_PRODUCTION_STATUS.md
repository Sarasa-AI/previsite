# RAG Production Status

Status as of the RAG completion phase on branch `version-4.0.0`.

## Verdict

| Environment | Ollama | Embeddings | Knowledge base |
|-------------|--------|------------|----------------|
| Local `docker-compose` | Yes — service `ollama` on port 11434 | Primary: Ollama `nomic-embed-text` (768-d) | Seed via `backend/scripts/seed_medical_knowledge.py` or admin ingest |
| Liara production (`sarasa-backend`) | **Not deployed** | **OpenRouter embeddings fallback** (same 768-d via `dimensions`) | Empty unless admin ingests curated docs |

**Decision:** Do **not** run Ollama as a Liara app in this phase. Use **option (b)** — OpenRouter embedding API behind `EmbeddingService`, with `EMBEDDING_PROVIDER=auto` (local) or `openrouter` (production).

## Why not Ollama on Liara?

1. [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`backend/liara.json`](backend/liara.json) only deploy the FastAPI backend + PostgreSQL + OpenRouter LLM. There is no Ollama service, env var, or model-pull step.
2. Ollama needs a long-running daemon and model storage (`nomic-embed-text`). Liara’s Python app runtime is not a suitable host for that process.
3. A separate Ollama VM/container is possible later, but it is outside the current two-app Liara architecture and would need monitoring, model pulls, and private networking.

Optional future path (not implemented): run Ollama on a dedicated host, set `OLLAMA_HOST` on `sarasa-backend`, pull `nomic-embed-text`, then set `EMBEDDING_PROVIDER=ollama` or `auto`.

## What was implemented

### Embedding providers ([`backend/app/services/embedding_service.py`](backend/app/services/embedding_service.py))

- `EMBEDDING_PROVIDER=auto` — try Ollama, then OpenRouter.
- `EMBEDDING_PROVIDER=ollama` — Ollama only.
- `EMBEDDING_PROVIDER=openrouter` — OpenRouter only (`OPENROUTER_EMBEDDING_MODEL`, request `dimensions=768` to match pgvector).
- Failures raise `EmbeddingServiceError` with a clear message (no silent empty vectors).

### Admin KB ingest

- `POST /api/admin/kb/ingest` (admin JWT) accepts JSON / Markdown / PDF.
- Requires `source`, `title`, and `published_at` for citation quality.
- Audit action: `kb_document_ingested`.
- **No LLM-generated medical content is added by this tooling.** Only curated documents approved by the clinical team should be uploaded.

### Reranker

- After pgvector cosine retrieval, optional CrossEncoder (`RERANKER_ENABLED`, default on in app config; off in pytest).
- Set `RERANKER_ENABLED=false` for immediate rollback if latency regresses.

### Doctor-visible citations

- SOAP keeps `[n]` markers after verification.
- Summary API returns enriched `soap_citations`; doctor summary UI shows hover/click popovers (amber warning when unverified).

## Production checklist (Liara)

1. Set env on `sarasa-backend`:
   - `EMBEDDING_PROVIDER=openrouter` (or `auto` if an external Ollama URL is later provided)
   - `OPENROUTER_API_KEY=...`
   - `OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small`
   - `RERANKER_ENABLED=true` (or `false` if needed)
2. Confirm Postgres has `pgvector` and migrations applied (`alembic upgrade head`).
3. Ingest curated KB documents via `POST /api/admin/kb/ingest` (do not rely on empty `medical_knowledge`).
4. Verify with admin `GET /health/detailed` — Ollama may show `down` on Liara; that is expected when using OpenRouter embeddings.
5. Generate a SOAP note and confirm `[n]` markers + popovers on `/summary/{sessionId}`.

## Local checklist

1. `docker compose up` (includes `ollama`).
2. `ollama pull nomic-embed-text`.
3. Optionally seed: `python backend/scripts/seed_medical_knowledge.py`.
4. Keep `EMBEDDING_PROVIDER=auto` so OpenRouter still helps if Ollama is down.
