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
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_IDLE_MINUTES=60
REFRESH_TOKEN_ABSOLUTE_DAYS=7
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
# MFA (optional). When true in production, FIELD_ENCRYPTION_KEY is required.
MFA_ENABLED=false
DOCTOR_MFA_REQUIRED=false
ADMIN_MFA_REQUIRED=false
FIELD_ENCRYPTION_KEY=
SINGLE_DOCTOR_MODE=false
# Metrics: admin JWT or optional static bearer. Unset in production → anonymous gets 404.
METRICS_BEARER_TOKEN=
# Consent enforcement (default off until legal copy is supplied)
CONSENT_ENFORCEMENT_ENABLED=false
# Account erasure cool-off (hours). Legal retention flags are placeholders — confirm with product owner.
ACCOUNT_DELETION_COOL_OFF_HOURS=72
LEGAL_RETENTION_KEEP_SESSION_SHELL=true
LEGAL_RETENTION_KEEP_PMH_SHELL=true
```

`SECRET_KEY` and `SEED_DOCTOR_PASSWORD` are required in production. Do **not** reuse local docker-compose defaults (`postgres`/`postgres`, `minioadmin`/`minioadmin`) — the backend exits on startup if those appear when `APP_ENV=production`.

### Privileged accounts (doctor / admin)

Public `POST /api/auth/register` **always** creates a patient. Never pass `role` from the client — it is ignored. Create doctors and admins with the operator CLI only (no HTTP endpoint):

```bash
cd backend
PYTHONPATH=. python scripts/create_privileged_user.py --role doctor --username otherdoc --password '...' \
  --license-number '...' --specialty '...' 
# Doctors are created as verification_status=pending unless --verified is passed.
PYTHONPATH=. python scripts/create_privileged_user.py --role doctor --username verifieddoc --password '...' --verified
PYTHONPATH=. python scripts/create_privileged_user.py --role admin --email admin@clinic.local --password '...'
```

The existing seed-doctor path (`SEED_DOCTOR_USERNAME` / `SEED_DOCTOR_PASSWORD`) is unchanged and is marked **verified** by migration.

### Session / refresh tokens (P2-A)

- Short-lived access JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15) in httpOnly `access_token` cookie.
- Rotating opaque refresh token (hash-at-rest) in separate httpOnly `refresh_token` cookie.
- `POST /api/auth/refresh` rotates; reuse of a rotated token revokes the whole family (audit `refresh_token_reuse`).
- `POST /api/auth/logout` / `logout-all` revoke family/all families. Frontend proxy retries once on 401 then clears cookies.
- Cleanup (no scheduler): `PYTHONPATH=. python scripts/cleanup_refresh_tokens.py`

### Patient OTP identity (P2-B)

- New patients register/login with **phone + OTP** (`POST /api/auth/otp/request`, `POST /api/auth/otp/verify`). Password self-register is disabled (`REGISTER_DISABLED`).
- Settings (names only): `SMS_PROVIDER`, `OTP_LOGIN_ENABLED`, `OTP_TTL_SECONDS`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_REQUEST_PER_PHONE_LIMIT`, `OTP_REQUEST_PER_PHONE_WINDOW_SECONDS`, `OTP_REQUEST_PER_IP_LIMIT`, `OTP_REQUEST_PER_IP_WINDOW_SECONDS`, `OTP_PHONE_DAILY_CAP`, `LEGACY_PATIENT_PASSWORD_LOGIN_ENABLED`.
- Providers: `console` (local only; refuses production), `test` (in-memory outbox), `http` (unimplemented stub). Production + `OTP_LOGIN_ENABLED` with console/test/http fails startup.
- Abuse limits: 120s TTL, 5 verify attempts, 60s resend cooldown, per-phone / per-IP windows, daily per-phone cap. Codes are hashed at rest; audits store last-3 + keyed hash only.
- **Legacy transition:** while `LEGACY_PATIENT_PASSWORD_LOGIN_ENABLED=true`, patients with national ID + password and no phone receive `PHONE_LINK_REQUIRED` + `link_token`; after OTP attach, history is preserved. When the flag is false, legacy login returns `LEGACY_LOGIN_DISABLED`.
- Doctors/admins: **email + password** only (+ MFA). Full-name login removed for all roles. Seeded doctor: `{SEED_DOCTOR_USERNAME}@doctor.com`.

### LLM de-identification gateway (P2-B)

- All external OpenRouter / GapGPT chat and embedding calls go through `app.privacy.llm_egress_gateway` (scrubber v1 + allow-list + metadata egress log).
- Settings: `EXTERNAL_LLM_DEIDENTIFICATION_ENABLED` (default true; production disable logs a startup warning), `ALLOW_EXTERNAL_IMAGE_INFERENCE` (default false), `EXTERNAL_LLM_PROVIDER_ALLOWLIST`, `LLM_SCRUB_DATE_MODE`, `LLM_EGRESS_LOG_RETENTION_DAYS`.
- Table `llm_egress_log` stores metadata only (no prompt/response). Cleanup: `PYTHONPATH=. python scripts/cleanup_llm_egress_log.py`.
- Consent key `external_llm_processing` remains **dormant** (not enforced). Product-owner `ai_processing` wording must disclose third-party providers.
- Residual risks: no ML NER (third-party names in free text); clinical narrative still egresses by design; image/raw-file egress unused today but gated off.

### Consent / privacy (P2-A)

- Consent records are append-only (`patient_consents`). Keys: `ai_processing`, `data_processing`, `recording`, `external_llm_processing`. Wording is **not** shipped — UI uses placeholder text keys only.
- `CONSENT_ENFORCEMENT_ENABLED=false` by default. When true, session create and intake/chat writes require current `ai_processing` + `data_processing`.
- Patient export: `POST /api/privacy/export` (async JSON bundle, time-limited download). Erasure: request → cool-off → admin approve → `scripts/execute_account_deletion.py`. **Legal retention rules must be confirmed by the product owner** (`LEGAL_RETENTION_*` are placeholders). Audit logs are never deleted.

### Doctor lifecycle (P2-A)

- Doctors have `verification_status`: `pending` | `verified` | `suspended`. Only **verified** doctors can claim/read patient sessions (`SINGLE_DOCTOR_MODE` unchanged for verified doctors).
- Admin APIs: list / verify / suspend / reinstate; MFA reset and backup-code regeneration (audited). Suspension revokes all refresh families.

### Schema migrations

**Alembic is the only schema source in production.** Do not run `create_all`, `add_is_hpi_complete_column.py`, or ad-hoc DDL against production. The start command already runs `alembic upgrade head`. Admin `GET /health/detailed` reports a `migrations` field (`ok` / `behind` / `unknown`).

Backend CI runs a Postgres service with `TEST_DATABASE_URL` and fails if `tests/test_alembic_integrity.py` is skipped.

### MFA field encryption

When `MFA_ENABLED=true` in production, set `FIELD_ENCRYPTION_KEY` to a Fernet key (name only in docs — never commit the value). Optionally encrypt legacy plaintext secrets once:

```bash
FIELD_ENCRYPTION_KEY=... PYTHONPATH=. python scripts/encrypt_mfa_secrets.py
```

### Rate limiting note

Sensitive-route rate limits (intake write, upload, PDF, OCR, medications search, MFA verify) use the **in-process** limiter. Limits are **not distributed** across workers/instances; do not rely on them alone for multi-replica abuse protection.

### Audit events (P1)

Patient-data access is audited (no clinical free text in audit fields): intake read/write, file upload/download/list, OCR read, PDF export, PMH overview read/write, non-self profile/overview read, admin clinical reads, and `session_access_denied` for failed session authorization. Query via `GET /api/admin/audit-logs`.

See `backend/.env.example` for the full list including `FIELD_ENCRYPTION_KEY` and per-route limit knobs.

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
- `access_token` is a short-lived JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15).
  Session continuity uses an opaque rotating `refresh_token` cookie (BFF sets
  httpOnly — never expose `refresh_token` to browser JavaScript). Idle lifetime:
  `REFRESH_TOKEN_IDLE_MINUTES` (default 60). Absolute family lifetime:
  `REFRESH_TOKEN_ABSOLUTE_DAYS` (default 7). Reuse of a rotated refresh token
  revokes the whole family. Operator cleanup (no scheduler):
  `python scripts/cleanup_refresh_tokens.py`