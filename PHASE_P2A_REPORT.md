# PHASE P2-A — Final Report

Date: 2026-10-02  
Scope: P1 closure, refresh-token sessions, consent structure, export/erasure, doctor lifecycle.

## Decisions

### Task 2 — MFA setup challenge
**Choice:** Server-side pending secret (`mfa_setup_challenges`), JWT carries only `challenge_id`.  
**Why:** A leaked setup token cannot reveal the TOTP secret; encryption reuses `field_crypto`; challenges are TTL-bound and single-use (consumed only after successful TOTP).

### Task 5 — Refresh tokens
**Choice:** Always issue rotating opaque refresh tokens (no kill-switch flag); lifetimes via settings.  
**Why:** Additive httpOnly cookie alongside the short-lived access JWT; clients that ignore refresh still work until access expiry. Defaults: idle 60 min, absolute 7 days, access JWT 15 min.

## Alembic / Postgres run (disposable container)

Container: `pgvector/pgvector:pg16` on `localhost:55432`, DB `previsit_alembic`.

```
$ python3 -m alembic upgrade head
→ completed to head v6e7f8g9h0i1

$ python3 -m pytest tests/test_alembic_integrity.py -v
tests/test_alembic_integrity.py::test_alembic_upgrade_head_matches_models_allowlist PASSED
tests/test_alembic_integrity.py::test_reconciliation_revision_downgrade_upgrade_smoke PASSED
============================== 2 passed in 2.03s ===============================
```

Allowlisted diffs (documented in `test_alembic_integrity.py`): pgvector embedding index shape; clinical_findings / recommendations / risk_signals UniqueConstraint vs unique index representation.

Fixes required for empty-DB upgrade:
- `0001_initial_schema.py`: `postgresql.ENUM(..., create_type=False)` after explicit `create(checkfirst=True)` (avoid double CREATE TYPE).
- `v6e7f8g9h0i1`: seed-doctor UPDATE uses `lower(CAST(role AS VARCHAR)) = 'doctor'` (PG enum labels are uppercase).
- Linearized migration chain: `t4 → u5 → v6` (Task 8 had briefly branched off `t4`).

CI: Backend workflow already has Postgres + `TEST_DATABASE_URL`; added explicit alembic-integrity step that fails if tests are skipped. Test helper fails (not skips) when `CI`/`GITHUB_ACTIONS` is set without `TEST_DATABASE_URL`.

## Files changed per task

### Task 1 — Chat POST authz
- `backend/app/api/chat.py` — patient-owner only for POST
- `backend/tests/test_p1_authz.py` — matrix updated (doctor/admin POST 403; GET OK)

**Caller check:** Only `frontend/app/chat/[sessionId]/page.tsx` posts messages. No doctor/admin UI depends on POST.

### Task 2 — MFA setup secret
- `backend/app/models/mfa_setup_challenge.py`
- `backend/alembic/versions/r2a3b4c5d6e7_add_mfa_setup_challenges.py`
- `backend/app/services/mfa_service.py`, `backend/app/api/routes/auth.py`
- `backend/tests/test_mfa.py`
- `backend/app/models/__init__.py`

### Task 3 — Metrics + dead code
- `backend/app/main.py`, `backend/app/core/config.py`
- `backend/tests/test_metrics_access.py`, `backend/tests/test_observability_propagation.py`
- **Removed:** `frontend/src/app/api/auth/login|logout|register|status/route.ts`, `frontend/src/app/api/proxy/[...path]/route.ts` (Next builds from `frontend/app/`)

### Task 4 — Alembic CI
- `.github/workflows/backend-ci.yml`
- `backend/tests/test_alembic_integrity.py`
- `backend/alembic/versions/0001_initial_schema.py` (enum create_type fix)

### Task 5 — Refresh tokens
- Models/service/migration/script/tests under `refresh_token*`
- Auth routes + schemas; frontend cookies, BFF refresh/logout/logout-all, proxy + axios single retry
- Settings: `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_IDLE_MINUTES=60`, `REFRESH_TOKEN_ABSOLUTE_DAYS=7`

### Task 6 — Consent
- `patient_consents` + `backend/app/privacy/*` + API + placeholder `/consent` page
- `CONSENT_ENFORCEMENT_ENABLED` default false
- Migration `t4c5d6e7f8g9`

### Task 7 — Export / erasure
- Privacy export jobs, deletion requests, services, admin approve, `execute_account_deletion.py`
- Migration `u5d6e7f8g9h0`
- Placeholders: `ACCOUNT_DELETION_COOL_OFF_HOURS=72`, `LEGAL_RETENTION_*` — **product owner must confirm legal retention**
- Phone column: N/A (does not exist on `users`)

### Task 8 — Doctor lifecycle
- User verification fields; admin doctor/MFA APIs; session_access gates; script flags
- Migration `v6e7f8g9h0i1`
- Flags: `DOCTOR_MFA_REQUIRED`, `ADMIN_MFA_REQUIRED` (default false)

### Task 9 — Docs
- `DEPLOYMENT.md`, `SECURITY_INCIDENT.md`, `backend/.env.example`

### Cross-cutting
- `backend/app/models/session.py` — SoapStatus bind by value for Postgres CI

## Tests (results)

| Suite | Result |
|-------|--------|
| `test_alembic_integrity.py` (disposable Postgres) | 2 passed |
| P2-A related (SQLite): p1_authz, mfa, metrics, refresh, consent, privacy, doctor_lifecycle, observability, migrations_health | **62 passed** |
| Postgres smoke (4 selected after SoapStatus fix) | 4 passed |
| Frontend `auth-cookies.test.ts` | 15 passed |

## Route authorization table (changed / added)

| Route | Patient | Doctor | Admin | Notes |
|-------|---------|--------|-------|-------|
| `POST /api/chat/{id}` | Owner only | 403 | 403 | Was doctor/admin writable |
| `GET /api/chat/{id}` | Owner | Verified + access | Access | Unchanged claim path |
| `GET /metrics` | — | 403 | JWT OK | Or `METRICS_BEARER_TOKEN`; prod anon → 404 if no token |
| `POST /api/auth/refresh` | Cookie | Cookie | Cookie | Rotation |
| `POST /api/auth/logout` | Auth | Auth | Auth | Revoke family |
| `POST /api/auth/logout-all` | Auth | Auth | Auth | Revoke all families |
| `GET/POST /api/consent/*` | Own | — | — | Grant/withdraw/list |
| `GET /api/consent/patient/{id}` | — | Verified + session | Session | Audited read |
| `POST /api/privacy/export` | Self | 403 | 403 | Rate limited |
| `GET /api/privacy/export/{job_id}` | Own job | 403 | 403 | |
| `POST /api/privacy/deletion-request` | Self + password | 403 | 403 | Cool-off starts |
| `POST /api/admin/privacy/deletion/{id}/approve` | 403 | 403 | After cool-off | |
| `GET /api/admin/doctors` | 403 | 403 | OK | |
| `POST /api/admin/doctors/{id}/verify\|suspend\|reinstate` | 403 | 403 | OK | Audited; suspend revokes refresh |
| `POST /api/admin/doctors/{id}/mfa/reset` | 403 | 403 | OK | Audited + revoke refresh |
| `POST /api/admin/.../regenerate-backup-codes` | 403 | 403 | OK | Audited |

Consent enforcement (when flag on): `POST /api/chat/session`, chat POST, intake writes → `CONSENT_REQUIRED` if missing current grants.

## Incomplete / follow-ups

- Full frontend CI lint/build not re-run end-to-end in this session (auth-cookie Vitest passed).
- Full backend pytest suite on Postgres CI should be green after SoapStatus values_callable fix; recommend confirming next Actions run.
- Legal retention and consent wording still require product-owner input.
- No password-change API yet; revoke-all is hooked for MFA reset/suspend (hook when password change is added).

## New risks noticed

- SoapStatus PG labels (lowercase) vs other enums (uppercase names) is inconsistent; values_callable on SoapStatus closes the CI failure but a future enum cleanup would reduce confusion.
- In-process rate limits remain non-distributed.
- Refresh tokens in JSON to BFF are stripped into httpOnly cookies; ensure no client ever logs full login responses.
- Account erasure keeps structural shells when `LEGAL_RETENTION_*` is true — confirm before production use.

## Feature flags / env (names only)

| Name | Default |
|------|---------|
| `CONSENT_ENFORCEMENT_ENABLED` | false |
| `DOCTOR_MFA_REQUIRED` | false |
| `ADMIN_MFA_REQUIRED` | false |
| `METRICS_BEARER_TOKEN` | unset |
| `REFRESH_TOKEN_IDLE_MINUTES` | 60 |
| `REFRESH_TOKEN_ABSOLUTE_DAYS` | 7 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 15 |
| `ACCOUNT_DELETION_COOL_OFF_HOURS` | 72 |
| `LEGAL_RETENTION_KEEP_SESSION_SHELL` | true (placeholder) |
| `LEGAL_RETENTION_KEEP_PMH_SHELL` | true (placeholder) |
| `CONSENT_VERSION_*` | v1 |
