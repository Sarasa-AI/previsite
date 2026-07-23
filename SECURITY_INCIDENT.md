# Security Incident: Exposed API Keys

**Status:** Keys identified and scrubbed from the working tree. History rewrite is prepared but **not executed**. Key revocation in vendor panels is a **manual** owner action.

## What was exposed

| Key | Prefix / pattern | Where found |
|-----|------------------|-------------|
| GapGPT API key | `sk-gp…` (full value previously in docs) | Working tree: [`MIGRATION.md`](MIGRATION.md) line 44. Introduced in commit `add0033` (“Initial MVP commit”). |
| OpenRouter API key | `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` | Git history only (removed from current tree earlier). Commits: `49fe475` (`frontend/openrouter-test.py`), `09d8970` (`backend/.env.example`). |

The GapGPT value in the current working tree has been replaced with the placeholder `<GAPGPT_API_KEY>`. The OpenRouter value is no longer in HEAD but remains reachable via `git show` on the commits above until history is rewritten.

## Manual checklist (owner / ops — do these yourself)

### 1. Revoke and rotate keys in vendor panels

- [ ] **OpenRouter:** Sign in to the OpenRouter dashboard → API Keys → revoke the leaked `sk-or-v1-…` key → create a new key.
- [ ] **GapGPT:** Sign in to the GapGPT dashboard → revoke the leaked `sk-gp…` key → create a new key.
- [ ] Update production secrets on Liara (and any staging/local `.env`) with the **new** keys only. Never commit real keys.
- [ ] Confirm old keys return auth errors when tested once (optional smoke check), then discard those test calls.

### 2. Confirm working-tree hygiene

- [ ] `MIGRATION.md` uses `<GAPGPT_API_KEY>` (or equivalent placeholder), not a real secret.
- [ ] `backend/.env` / `frontend/.env*` are gitignored and not tracked (`git ls-files '*.env'` should be empty for secret files).
- [ ] Run `./scripts/clean-repo-secrets.sh` (section A) if any env/credential files are still tracked.

### 3. History rewrite (coordinate with all collaborators first)

Rewriting history requires a force-push and every clone to be re-cloned or carefully reset. **Do not run this alone on a shared remote without team agreement.**

- [ ] Notify all collaborators: stop pushing; expect force-push on the affected branches.
- [ ] Install tooling if needed: `pip install git-filter-repo` or `brew install git-filter-repo` (BFG is an alternative; this repo’s script targets `git-filter-repo`).
- [ ] On a fresh clone, review then run: `./scripts/clean-repo-secrets.sh --rewrite-history` (see script help). Default mode is dry-run / documentation only until you pass the explicit flag.
- [ ] Force-push rewritten branches **only after** team acknowledgment.
- [ ] Have every collaborator delete their old local clone or hard-reset to the rewritten remote (do not merge old history back).

### 4. Post-rotation verification

- [ ] Backend on Liara starts with new `OPENROUTER_API_KEY` / `GAPGPT_API_KEY`.
- [ ] Intake / SOAP LLM paths work with the new keys.
- [ ] No real `sk-or-v1-` / `sk-gp` values appear in `git grep` on HEAD.

## Finding: single-doctor clinic vs multi-doctor RBAC

The product has historically behaved as a **single-doctor clinic**: any authenticated doctor could see all patient sessions because `sessions.doctor_id` was never set. Resource-level RBAC (claim-on-open + `SINGLE_DOCTOR_MODE`) is implemented separately so multi-doctor isolation can be enforced when `SINGLE_DOCTOR_MODE=false` (default).

## Remaining risks (deferred to later phases)

Intentionally **not** addressed yet (or only partially):

- Git history rewrite not executed yet (requires team coordination + force-push; see checklist above)
- Central secret manager (Vault / cloud KMS) — env-based secrets only for now
- Encryption at rest / field-level PHI encryption (MFA secrets stored in DB without field-level encryption)
- Free-text SOAP edit API exists as `PATCH /api/sessions/{id}/soap` (overwrite + `previous_value` on audit); full Inline Edit / Track Changes UI remains Phase 4
- Admin UI for audit logs (API only: `GET /api/admin/audit-logs`)
- Distributed/multi-instance auth rate limiting (current limiter is in-memory per process)
- Manual key rotation in OpenRouter / GapGPT panels (owner checklist above)
- GitHub branch protection required checks must be enabled manually after first green Actions runs (`Backend CI` / `Frontend CI`)

### Addressed in quality phase (this branch)

- CI/CD via GitHub Actions (backend Postgres + Alembic + pytest; frontend lint/build/Vitest)
- Backend coverage visibility (`pytest-cov` artifact) and frontend Vitest suite for critical UI paths
- Optional Sentry (`SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN`) and admin `GET /health/detailed`
- Doctor MFA/TOTP behind `MFA_ENABLED` (default off; enrollment + backup codes; no lockout until doctor completes setup)
