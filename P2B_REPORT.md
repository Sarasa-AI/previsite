# P2-B Final Report — OTP Identity + LLM De-identification Gateway

## 1. Discovery findings (Task 3 — before code changes)

All live external inference went through **OpenRouter** (primary) and optionally **GapGPT** (tier-2). No production path sent images or raw file bytes. OCR was local.

| # | Path | Provider | Fields sent | Images? | Fallback |
|---|------|----------|-------------|---------|----------|
| 1 | Intake L2 HPI | OpenRouter → GapGPT/OR | Age, Sex, Chief Complaint | No | Tier-3 templates |
| 2 | Intake L3 summary | same | Age/Sex/CC + HPI answers | No | Tier-3 factories |
| 3 | Chat interview | same | Full history + clinical_context | No | Static question |
| 4 | Chat summary | same | Conversation transcript | No | Heuristic summary |
| 5 | SOAP | OpenRouter direct | Structured summary, PMH, messages, file text, RAG | No | Error status |
| 6 | RAG embed | OpenRouter `/embeddings` | Query text | No | Continue without evidence |
| 7 | KB ingest embed | OpenRouter `/embeddings` | Chunk text | No | HTTP 503 |
| 8 | Document intelligence | OpenRouter chat | OCR extraction lines | No | Per-artifact error |
| 9 | Health/startup | OpenRouter `models.list` | None | No | Startup fail / skip |

**Not external:** local OCR, local CrossEncoder rerank, unused `encode_image_to_base64`.

After P2-B, all of the above chat/embed/health paths route through `app.privacy.llm_egress_gateway`.

---

## 2. Files changed (by task)

### Task 1 — OTP backend
- Models: `otp_challenge.py`, `llm_egress_log.py`, `user.py` (phone, nullable password)
- Migration: `w7f8g9h0i1j2_add_otp_phone_and_llm_egress.py`
- SMS: `app/services/sms/__init__.py` (Console / Test / Http stub)
- OTP: `app/services/otp_service.py`, `app/utils/phone.py`
- Auth: `app/api/routes/auth.py`, `app/auth/schemas.py`, `app/core/config.py`
- Tests: `test_otp_auth.py`, `test_phone_normalize.py`, `tests/auth_helpers.py` + login helper updates
- `.env.example`

### Task 2 — OTP frontend
- `PatientLoginForm.tsx` (phone → OTP), `register/page.tsx`, `DoctorLoginForm.tsx` (email)
- BFF: `app/api/auth/otp/request`, `otp/verify`; login passes `phone_link_required`
- `lib/phone.ts`, `lib/otp-errors.ts` + Vitest updates

### Task 3 — Gateway
- `app/privacy/scrubber.py`, `app/privacy/llm_egress_gateway.py`
- Rewired: `openrouter_service`, `tier2_llm_client`, `embedding_service`, `soap_generator`, OpenRouter inference client, startup/health probes
- Consent dormant comment; `scripts/cleanup_llm_egress_log.py`
- Tests: `test_llm_egress_gateway.py` (scrubber, allow-list, image block, scan, egress columns)

### Task 4 — Docs
- `DEPLOYMENT.md`, `SECURITY_INCIDENT.md`, this report

---

## 3. Route authorization table (changed/added)

| Method / path | Who | Notes |
|---------------|-----|-------|
| `POST /api/auth/otp/request` | public | Rate-limited; enumeration-safe |
| `POST /api/auth/otp/verify` | public | Issues patient session (access + refresh) |
| `POST /api/auth/login` | public | Doctor/admin: email+password (+ MFA). Legacy patient: national_id+password when flag on |
| `POST /api/auth/register` | public | Returns `REGISTER_DISABLED` (410) |
| MFA / refresh / logout / me | unchanged | |

**Seeded doctor login:** `bagherzade@doctor.com` + `SEED_DOCTOR_PASSWORD` (tests: `0808`).

---

## 4. Tests

### Backend (SQLite local)
- `pytest tests/test_phone_normalize.py tests/test_otp_auth.py` → pass
- `pytest tests/test_llm_egress_gateway.py` → pass (after scan fix)

### Backend (Postgres)
- Run with `TEST_DATABASE_URL=postgresql+asyncpg://…` in CI (`backend-ci.yml`). Empty-DB Alembic upgrade remains covered by `test_alembic_integrity.py` (new head `w7f8g9h0i1j2`).

### Frontend
- Vitest: digit conversion, OTP error mapping, resend timer, doctor email payload

---

## 5. NOT covered by de-identification

- Clinical free text / HPI answers / chat transcripts (still sent after identifier scrub)
- Third-party names in free text (no ML NER)
- Numeric internal `patient_id` / session ids in some SOAP contexts
- Admin KB ingest chunk content (scrubbed for regex categories only; no “known patient” context)
- Local OCR / local reranker (never left the system)

---

## 6. Not completed / follow-ups

- Real SMS HTTP provider (stub only)
- Frontend legacy `PHONE_LINK_REQUIRED` attach UI (API ready; primary patient path is OTP)
- Distributed OTP rate limits (in-process only, same as other auth limits)
- Postgres CI run results for this branch should be confirmed in GitHub Actions after push

---

## 7. New risks

- OTP SMS cost / abuse if a real provider is misconfigured without limits
- Console SMS in non-production still logs masked phone (never code)
- Disabling `EXTERNAL_LLM_DEIDENTIFICATION_ENABLED` in production only warns — operators must not leave it off
- Legacy password login remains until `LEGACY_PATIENT_PASSWORD_LOGIN_ENABLED=false`
