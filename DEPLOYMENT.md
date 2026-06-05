# PreVisit MVP Deployment Guide

## 1) Local Production-Like Run (Docker Compose)

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## 2) Backend Deployment (Railway or Render)

Build/Run:
- Build command: `pip install -r requirements.txt`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Required environment variables:
- `DATABASE_URL=postgresql+psycopg2://...`
- `SECRET_KEY=<very-long-random-secret>`
- `ALGORITHM=HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES=1440`
- `LLM_PROVIDER=openai` or `anthropic`
- `OPENAI_API_KEY=...` (if openai)
- `ANTHROPIC_API_KEY=...` (if anthropic)
- `CORS_ORIGINS=https://your-frontend-domain`
- `APP_ENV=production`
- `LOG_LEVEL=INFO`
- `CHAT_RATE_LIMIT_REQUESTS=20`
- `CHAT_RATE_LIMIT_WINDOW_SECONDS=60`

## 3) Frontend Deployment (Vercel)

Framework preset: Next.js

Environment variables:
- `BACKEND_API_URL=https://your-backend-domain`
- `NEXT_PUBLIC_APP_NAME=PreVisit MVP`

After deploy:
- Verify login/register APIs through `/api/auth/*`
- Verify proxy routes under `/api/proxy/*`

## 4) HTTPS and Security Checklist

- Use platform-managed HTTPS certificates (Vercel/Railway/Render).
- Set strong `SECRET_KEY` and rotate it periodically.
- Keep auth cookie `httpOnly` and `secure` in production.
- Restrict CORS to known frontend domains only.
- Use managed PostgreSQL with backups enabled.

## 5) E2E Execution

From `frontend/`:

```bash
npm install
npx playwright install
E2E_BASE_URL=http://127.0.0.1:3000 npm run test:e2e
```

Main flow:
- Register -> Login -> Create session -> Chat -> Upload file -> Summary
