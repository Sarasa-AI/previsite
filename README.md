# PreVisit MVP

## Overview

PreVisit MVP is a two-tier application for collecting a pre-visit medical history before a clinician encounter.

- Frontend: `Next.js 14` app with auth routes, protected pages, and a backend proxy.
- Backend: `FastAPI` app with JWT auth, session-based chat, file upload, and summary endpoints.
- Storage: SQLAlchemy models for users, sessions, messages, files, and summaries.

## Implemented MVP Scope

### User Registration

- `POST /api/auth/register` creates patient accounts.
- Email and minimum password validation are enforced with Pydantic.
- User roles are now validated against supported enum values.

### Login Authentication

- `POST /api/auth/login` validates credentials and returns a JWT access token.
- Frontend auth route stores the token in an `httpOnly` cookie.
- Secure-cookie behavior now follows the actual request protocol so local HTTP login works during production-mode `next start`.

### Session Management

- Authenticated patients can create sessions through `POST /api/chat/session`.
- Authenticated patients can list their own sessions through `GET /api/chat/sessions`.
- Session ownership is enforced across chat, upload, and summary endpoints.

### Chat Functionality

- Authenticated patients can send messages to `POST /api/chat/{session_id}`.
- Message history is available through `GET /api/chat/{session_id}`.
- The chat flow uses staged interview prompts to keep the conversation aligned to the medical intake sequence.
- When external LLM credentials are not available, the backend now falls back to deterministic prompts instead of failing the full request path.

### File Upload

- Authenticated patients can upload supported files through `POST /api/files/{session_id}/upload`.
- Allowed extensions are enforced in the backend.
- Invalid file types now correctly return `400` instead of being converted into generic `500` responses.

### Summary Generation

- Summaries are stored per session and served through `GET /api/summary/{session_id}`.
- Summary existence is available through `GET /api/summary/session/{session_id}/exists`.
- Summary ownership checks were tightened to avoid leaking session information across users.
- SOAP generation now receives the correct schema shape and updates the stored summary when a SOAP note is produced.
- When external LLM services are unavailable, a fallback summary is generated from the patient conversation so the MVP flow still completes.

## API Surface

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`

### Chat and Sessions

- `POST /api/chat/session`
- `GET /api/chat/sessions`
- `POST /api/chat/{session_id}`
- `GET /api/chat/{session_id}`

### Files

- `POST /api/files/{session_id}/upload`

### Summaries

- `GET /api/summary/{session_id}`
- `GET /api/summary/session/{session_id}/exists`

## Key Audit Fixes

- Added role validation for user registration and aligned the default role to `patient`.
- Added inactive-user protection during login.
- Added a compatibility `detail` field to structured backend error responses so frontend pages can show useful errors.
- Added robust frontend error parsing for login, register, dashboard, chat, upload, and summary views.
- Fixed local session cookie handling under `next start`.
- Deferred LLM client initialization so missing API keys do not crash app import or startup.
- Added chat and summary fallbacks for environments without LLM credentials.
- Fixed file upload error propagation for invalid extensions.
- Fixed summary authorization for both retrieval and existence checks.
- Fixed SOAP generation input mapping so the generated note can be persisted.
- Replaced deprecated SQLAlchemy and Pydantic patterns where straightforward.

## Test and Verification Results

### Backend

- `python -m pytest -q`
  - Result: `147 passed, 5 failed` (failures are pre-existing LLM resiliency / HPI contract flakes in `test_api_integration.py`, unrelated to this security phase)
- `python -m compileall app tests`
  - Result: success

### Frontend

- `npm run lint`
  - Result: success
- `npm run build`
  - Result: success

### Integration

- Local backend started successfully with:

```bash
env DATABASE_URL=sqlite:///./previsit_local.db OPENAI_API_KEY='' ANTHROPIC_API_KEY='' uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Local frontend started successfully with:

```bash
env BACKEND_API_URL=http://127.0.0.1:8000 npm run start
```

- Full HTTP integration flow validated against the running local stack:
  - register
  - login
  - create session
  - send chat message
  - fetch chat history
  - upload file
  - fetch summary

## Assumptions

- The MVP scope is the repository flow documented in `DEPLOYMENT.md`: register -> login -> create session -> chat -> upload file -> summary.
- Patients are the primary user role for the MVP flow.
- File upload scope covers secure upload, validation, and persistence; deeper medical file analysis is not required for every upload to complete the base MVP flow.
- Summary generation may operate in a degraded fallback mode when external LLM credentials are unavailable.
- SQLite is acceptable for local validation, while PostgreSQL remains the intended deployment database.
- `docker-compose.yml` defaults (`postgres`/`postgres`, `minioadmin`/`minioadmin`) are **local development only**. Never use them when `APP_ENV=production` — the backend refuses to start with those defaults in production.

## Remaining Blockers

- Playwright browser binaries are not installed locally, and `npx playwright install chromium` currently fails due network TLS reset errors. This prevents the browser-based E2E suite from executing in this environment.
- The repository root is not a Git repository in the current environment, so the requested per-task commits cannot be created here.
- Coverage tooling is not installed for Python, and no frontend coverage tool is configured, so an actual numeric `90%` coverage report could not be generated in this environment.
- Full remote deployment was not completed because no target hosting credentials, CI environment, or deployment destination were provided in the workspace.
- The tracked local backend `.env` should not be treated as deployable configuration and any real secrets stored there should be rotated and removed from versioned workflow usage.

## Local Run

### Backend

```bash
cd backend
python -m pytest -q
env DATABASE_URL=sqlite:///./previsit_local.db OPENAI_API_KEY='' ANTHROPIC_API_KEY='' uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
env BACKEND_API_URL=http://127.0.0.1:8000 npm run start
```

## Deliverables

- Backend reliability fixes for auth, sessions, chat, files, and summaries
- Frontend session-cookie and error-handling fixes
- Backend MVP route tests
- Updated deployment and operational documentation in this README and `DEPLOYMENT.md`
# previsite
