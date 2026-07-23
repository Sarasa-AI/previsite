# PreVisit MVP — Liara Deployment Guide

This project is a **FastAPI** backend (`./backend`) and a **Next.js 14** frontend (`./frontend`).

Deploy them as **two separate Liara apps**:

| App name | Directory | Platform | URL |
|---|---|---|---|
| `sarasa-ai` | `./frontend` | Node 22 | https://sarasa-ai.liara.run |
| `sarasa-backend` | `./backend` | Python 3.11 | https://sarasa-backend.liara.run |

**Do not run `liara deploy` from the repo root** — there is no root `package.json`. Always deploy from the app directory.

---

## Prerequisites

1. [Liara CLI](https://docs.liara.ir/cli/install) installed and logged in:
   ```bash
   liara login
   ```
2. Two Liara apps created in the console:
   - `sarasa-ai` (Node)
   - `sarasa-backend` (Python)
3. A Liara **PostgreSQL** database for the backend.

---

## 1) Deploy backend (`sarasa-backend`)

```bash
cd backend
liara deploy --app sarasa-backend --port 8000 --platform python
```

`backend/liara.json` and `backend/Procfile` are already configured:

- **Platform:** Python 3.11 (`runtime.txt`)
- **Port:** 8000
- **Start command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Backend environment variables (Liara console → sarasa-backend → Environment)

Set these in the Liara dashboard (or via CLI):

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE
SECRET_KEY=<long-random-secret>
SEED_DOCTOR_USERNAME=bagherzade
SEED_DOCTOR_PASSWORD=<strong-doctor-password>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
APP_ENV=production
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://sarasa-ai.liara.run
LOG_LEVEL=INFO
SKIP_HEALTH_CHECK=true
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-key>
OPENROUTER_DEFAULT_MODEL=qwen/qwen-2.5-72b-instruct
OPENROUTER_HTTP_REFERER=https://sarasa-ai.liara.run
OPENROUTER_APP_TITLE=PreVisit MVP
UPLOAD_DIR=./uploads
# RAG embeddings (Liara has no Ollama service — use OpenRouter or auto fallback)
EMBEDDING_PROVIDER=openrouter
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
# Optional: set false to disable CrossEncoder rerank if latency is a concern
RERANKER_ENABLED=true
```

`SECRET_KEY` and `SEED_DOCTOR_PASSWORD` are required in production. Do **not** reuse local docker-compose defaults (`postgres`/`postgres`, `minioadmin`/`minioadmin`) — the backend exits on startup if those appear when `APP_ENV=production`.

See `backend/.env.example` for the full list.

### Verify backend

```bash
curl https://sarasa-backend.liara.run/health
```

Expected:

```json
{"status":"ok"}
```

---

## 2) Deploy frontend (`sarasa-ai`)

```bash
cd frontend
liara deploy --app sarasa-ai --port 3000 --platform node
```

`frontend/liara.json` pins **Node 22 LTS** (avoids npm "Exit handler never called" on Node 24).

### Frontend environment variables (Liara console → sarasa-ai → Environment)

```env
BACKEND_API_URL=https://sarasa-backend.liara.run
NEXT_PUBLIC_APP_NAME=PreVisit MVP
```

`BACKEND_API_URL` is used **server-side only** by Next.js API routes (`/api/auth/*`, `/api/proxy/*`). The browser never calls `localhost:8000` directly.

See `frontend/.env.example`.

### Verify frontend

1. Open https://sarasa-ai.liara.run
2. Register / log in
3. Create a chat session and send a message

---

## Architecture

```
Browser  →  https://sarasa-ai.liara.run/api/proxy/...
                ↓ (Next.js server route, BACKEND_API_URL)
            https://sarasa-backend.liara.run/api/...
                ↓ (FastAPI)
            PostgreSQL + OpenRouter LLM
```

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit values
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # BACKEND_API_URL=http://localhost:8000
npm run dev
```

Frontend: http://localhost:3000  
Backend: http://localhost:8000

---

## Docker Compose (optional local prod-like run)

```bash
docker compose up --build
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `liara deploy` fails at repo root | Deploy from `./frontend` or `./backend` |
| Frontend 502 / "Backend is unreachable" | Set `BACKEND_API_URL` on `sarasa-ai` to the backend URL |
| CORS errors | Ensure `CORS_ORIGINS` on backend includes `https://sarasa-ai.liara.run` |
| Backend won't start (LLM check) | Set `SKIP_HEALTH_CHECK=true` until OpenRouter key is configured |
| npm install fails on Liara | Confirm Node 22 in `frontend/liara.json` and `engines.node` in `package.json` |
| Backend deploy expects Node/npm | Deploy from `./backend` with `--platform python`, not from root |

---

## Security checklist

- Use strong `SECRET_KEY` on the backend
- Never commit `.env` files
- Restrict `CORS_ORIGINS` to known frontend domains
- Auth cookies are `httpOnly`; `secure` is set automatically on HTTPS
