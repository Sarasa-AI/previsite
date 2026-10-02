# PreVisit Runtime Repair & Verification Report

Date: 2026-08-28
Phase: Runtime confirmation
Scope: BREAK A (doctor route bypass), BREAK C (builder fail-before-evidence),
runtime confirmation of the deterministic Workspace labs path.

Evidence classes, never mixed:

| Class | Meaning |
|---|---|
| **STATIC** | Read from source. Locates where the path *should* run. |
| **TEST** | A test executed, with observed output. |
| **RUNTIME** | A real endpoint/process executed and produced observed output. |
| **BROWSER** | Real rendered DOM / screenshot at a stated URL. |

---

## Executive Verdict

```
CONDITIONAL GO
```

**Reason.** The entire backend clinical path is now **runtime-confirmed against the
real application**, from an HTTP multipart upload through to the Workspace API,
with the extracted laboratory value observed at every stage. What remains
unconfirmed is the **final browser layer only** — browser rendering of the labs
card and runtime traversal of the repaired doctor route — blocked by the
tool-safety classifier outage, not by any discovered defect.

Per §24, `CONDITIONAL GO` is the defined verdict when "the core runtime path is
confirmed but a genuinely non-critical final layer, such as browser automation
availability, prevents one final confirmation."

**Exactly what remains UNKNOWN:**

1. Browser rendering of the Workspace shell and Labs card.
2. Runtime traversal of `/doctor-dashboard` → `/clinician/{id}/workspace`
   (the source change is applied; no browser executed it).
3. The repo-wide `/clinician/` grep, so a stray non-canonical link elsewhere in
   the frontend cannot be excluded.
4. Full-suite regression status after the two repairs.

Nothing else on the acceptance path is UNKNOWN.

---

## What was proven at runtime

```
$ cd backend && python3 -m pytest tests/test_workspace_labs_e2e.py -q -s
2 passed in 1.81s
```

The real application: real HTTP multipart upload → real background document
pipeline → real pypdf text-layer read → real deterministic extraction → real
persisted artifacts → real doctor login → real `ClinicalContextBuilder` (no
dependency override) → real `clinical-content` → real `workspace`. No mocked
clinical data, no injected `lab_evidence`, no hardcoded value, no auth bypass.

**Notably, the session carried no Intake and no Summary row** — the SELECTs for
both returned empty in the logs. That is precisely the BREAK C condition, now
succeeding through the real HTTP API rather than a direct builder call.

Only the canonical pipeline ran: the upload passed `condition_id: null`, so the
legacy synchronous OCR block was skipped entirely.

---

## Final Evidence Table

| Stage | Status | Exact Runtime Evidence |
|---|---|---|
| Backend boot | **CONFIRMED** | Real FastAPI app served in-process via `ASGITransport`; every request logged by `CorrelationIdMiddleware`. |
| Database | **CONFIRMED** | SQLite via conftest; `CREATE TABLE` DDL for all 17 tables in log, then real INSERT/SELECT traffic. |
| Authentication | **CONFIRMED** | `POST /api/auth/register status=200`; patient `POST /api/auth/login status=200` (`user_id=2 role=patient`); doctor `Login lookup succeeded login_id='bagherzade' user_id=1 email='bagherzade@doctor.com' role=doctor`, `status=200`. Authorization enforced, not bypassed. |
| Session | **CONFIRMED** | `POST /api/chat/session status=200 duration_ms=6`, session id `1`, `doctor_id=None`. |
| Upload | **CONFIRMED** | `POST /api/files/1/upload status=200 duration_ms=7`; body `{"id":1,"filename":"pv-test-84721.pdf","file_path":"1/20260828202408_pv-test-84721.pdf","size":823,"mime_type":"application/pdf","condition_id":null}`. |
| Processing trigger | **CONFIRMED** | Background task executed: idempotency probe `SELECT document_artifacts.kind WHERE file_id=1`, then `document_pipeline:process_document_artifacts:239 Document processed`. |
| OCR / text extraction | **CONFIRMED** | Artifact `kind='ocr' status='succeeded' engine='pypdf-text-layer' engine_version='pypdf' page_count=1`, `raw_text='CBC Laboratory Report\nPatient ID: PV-TEST-84721\nDate: 2026-08-20\nHemoglobin: 13.7 g/dL\nWBC: 8,421 /uL\nPlatelets: 245,000 /uL'`. Application-invoked; needed neither Tesseract nor Poppler. |
| Clinical extraction | **CONFIRMED** | Artifact `kind='extraction' status='succeeded' engine='deterministic-line-regex' v1.0.0`; values `Hemoglobin/13.7/g/dL`, `WBC/8,421//uL`, `Platelet/245,000//uL`; each `needs_review=false`, `abnormal=false`, provenance `source_text='Hemoglobin: 13.7 g/dL'`, `page=1`, `method='deterministic-line-regex'`. |
| DocumentArtifact | **CONFIRMED** | Two rows persisted and committed: `[{"kind":"ocr","status":"succeeded","engine":"pypdf-text-layer","error":null},{"kind":"extraction","status":"succeeded","engine":"deterministic-line-regex","error":null}]`. |
| ClinicalContextBuilder | **CONFIRMED (via real API)** | The `clinical-content` request ran the real builder — logged SELECTs on sessions, messages, summaries (empty), intakes (empty), patient_pmh, files, document_artifacts — and returned 200. No dependency override. |
| lab_evidence | **CONFIRMED** | Row id `doc-1-hemoglobin` present in the projected labs, derived from the document artifact. |
| Clinical Content API | **CONFIRMED** | `GET /api/sessions/1/clinical-content status=200 duration_ms=13`; labs rows: `{"id":"doc-1-hemoglobin","name":"Hemoglobin","value":"13.7 g/dL","unit":"","reference_range":"","abnormal":false,"trend":"unknown","detail":"13.7 g/dL"}` plus Platelet and WBC rows. |
| Workspace API | **CONFIRMED** | `GET /api/sessions/1/workspace status=200 duration_ms=21`; `ETag=e45bf0c6292eb317c1beb40febdabed0bf3395b8b641b4fcedf9d88a28d27cea`, `X-Contract-Version=1.0.0`; labs directive `{"object_id":"labs","priority":"p2","slot":"secondary","size":"standard","pinned":false,"visibility_reason":null}` — visible, not hidden, no empty-content fallback. |
| Fail-closed boundary | **CONFIRMED** | Empty session → `GET /api/sessions/1/clinical-content status=404`, `detail="WORKSPACE_SESSION_NOT_FOUND"`. The BREAK C repair did not weaken the safety floor. |
| Doctor route | **UNKNOWN** | Source repaired (`PatientFileCard.tsx:78`) and read back; no browser navigation executed; repo-wide grep unrun. |
| Browser Workspace | **UNKNOWN** | No browser launched. |
| Labs card | **UNKNOWN** | Never rendered. |
| Actual lab value (end-to-end to screen) | **UNKNOWN** | Confirmed to the Workspace API; not observed in a DOM. |

---

## Final Value Assertion

```
Test artifact:
  Hand-assembled single-page text-layer PDF, 823 bytes, uploaded over real HTTP
  multipart as "pv-test-84721.pdf" (application/pdf). Built in test code only
  (tests/test_workspace_labs_e2e.py). No PV-TEST-84721 fixture exists in the
  repository — TEST ARTIFACT = NOT FOUND, and none was invented. The value
  appears nowhere in production code.

Expected clinical value encoded in artifact:
  Hemoglobin: 13.7 g/dL   (plus WBC: 8,421 /uL, Platelets: 245,000 /uL)

Observed extracted value (application OCR + extraction, runtime):
  name="Hemoglobin"  value="13.7"  unit="g/dL"  needs_review=false
  source_text="Hemoglobin: 13.7 g/dL"  page=1  method="deterministic-line-regex"

Clinical Content API value (runtime):
  {"id":"doc-1-hemoglobin","name":"Hemoglobin","value":"13.7 g/dL","unit":""}
  NOTE: the projection folds the unit into `value` and returns unit="".
  The separate unit "g/dL" is preserved at the extraction/provenance layer.
  Reported exactly as observed — not normalised to make it look cleaner.

Workspace value (runtime):
  The plan exposes the labs card, not row values: object_id="labs",
  slot="secondary", priority="p2", visibility_reason=null. Card bodies are
  served by clinical-content (above), which is the architecture as designed.

Browser-rendered value:
  UNKNOWN — no browser evidence.

Final consistency (artifact → OCR → extraction → context → clinical-content API):
  CONFIRMED
Final consistency (→ browser):
  UNKNOWN
```

---

## Break A — Doctor route bypassed the canonical Workspace

**Root cause.** Navigation wiring only; REALITY_AUDIT §5 *"Route bypass"*. The
workspace was complete and mounted, and the only doctor-facing session link
pointed at its legacy predecessor.

**Fix applied.** `frontend/components/clinician/PatientFileCard.tsx:78`:

```diff
- href={`/clinician/${session.id}`}
+ href={`/clinician/${session.id}/workspace`}
```

**Legacy route made explicit.** `/clinician/{id}` stays reachable by bookmark and
back-navigation and still owns session PDF export, so
`frontend/app/clinician/[sessionId]/page.tsx` now renders a primary link to
`/clinician/${sessionId}/workspace` beside the PDF button instead of being a
silent dead-end.

> ⚠️ **Copy needs native review** — new label `میزکار بالینی`. Per `CLAUDE.md` §9,
> Persian medical register is a native-speaker call. Navigation copy only.

**Status: UNKNOWN at runtime.** Source verified by reading; no browser traversal;
repo-wide grep unrun.

---

## Break C — Builder raised before document evidence was projected

**Root cause.** Statement ordering: `build()` raised
`ValueError("No clinical summary available for ClinicalContext")` ten lines before
document/lab evidence was loaded. Both workspace dependencies
(`api/dependencies.py:149-152`, `:220-223`) map that to
`404 WORKSPACE_SESSION_NOT_FOUND`, so a session holding extracted labs reported as
non-existent.

**Fix applied.** Evidence derivation moved above the guard; the guard now tests
for real evidence, and the placeholder invents nothing (`MedicalSummary` has no
required fields — `app/schemas/medical.py:33-65`):

```python
if not med_sum:
    if not (lab_evidence or medication_evidence or document_evidence):
        raise ValueError("No clinical summary available for ClinicalContext")
    med_sum = MedicalSummary()
```

| Case | Condition | Behaviour | Runtime status |
|---|---|---|---|
| A | no summary + evidence present | minimal context, evidence preserved | **CONFIRMED** — clinical-content 200 with Hemoglobin, on a session with no Intake and no Summary |
| B | no summary + no evidence | `ValueError` → 404 | **CONFIRMED** — `404 WORKSPACE_SESSION_NOT_FOUND` |
| C | summary present | unchanged | Covered by the pre-existing builder suite; full sweep not yet rerun |

**Builder-level regression** (`tests/test_clinical_context_document_only.py`):
`2 passed in 1.36s`.

**Why no pre-existing test caught this.** `test_workspace_api.py:172` overrides
`resolve_clinical_context`; `test_clinical_content_api.py:167` overrides
`resolve_clinical_content_inputs` — both replace the dependency that calls the
builder. The one suite calling the real builder
(`test_soap_clinical_context.py:188`) seeds a summary in every case.

**Status: CONFIRMED**, at both the builder level and through the real HTTP API.

---

## Inference Re-Verification

| Claim | Static | Runtime | Affects Workspace Labs? |
|---|---|---|---|
| Runtime init | Wired — `main.py:48-51` (lifespan) | **BROKEN in this harness** — `RuntimeError: Inference runtime not initialized. Call init_inference_runtime() at startup.` (`composition.py:135`). Expected: `ASGITransport` does not run the lifespan. Production behaviour UNKNOWN. | **No** |
| OpenRouter registration | Key-gated, no fake fallback | NOT REACHED (no key in harness) | **No** |
| Intelligence pipeline | Wired | **Executed and failed soft** — `Failed to process artifact 1 for session 1`, then `pipeline completed for session 1: 0/1 processed` | **No** |
| Document → Intelligence | Wired — `document_pipeline.py:298` | **CONFIRMED triggered** — the task ran (and failed at the inference step) | **No** |
| OpenRouter extraction | Present, not the labs source | NOT REACHED | **No** |
| Workspace intelligence signals | Wired — `dependencies.py:155-168` | Executed — `SELECT ... FROM clinical_findings WHERE session_id=1` returned none | **Indirect only** |

**Orthogonality is now RUNTIME-PROVEN, not merely argued.** In the same request
cycle, the inference branch raised `RuntimeError` and produced zero findings,
while the labs path delivered `Hemoglobin 13.7 g/dL` to the Workspace API. The
deterministic path does not depend on inference. All six prior "fixes" live on the
findings branch and none of them could have made a lab value appear.

---

## New findings from runtime evidence

1. **Trust provenance mislabels document-derived labs.** The labs directive
   reports `primary_provenance: "patient_reported"` for a value transcribed from
   an uploaded document, although `TrustProvenance.DOCUMENT_OCR` exists
   (`domain/enums.py:62`). A physician reading the trust descriptor would be told
   the wrong origin. **Not fixed** — it is off the acceptance path and changing
   trust semantics warrants its own review and diff. Flagged, with evidence.
2. **Unit is folded into the lab value string.** `_project_labs` emits
   `value="13.7 g/dL"`, `unit=""`, discarding the structured unit that extraction
   captured (`unit="g/dL"`). Harmless for display, but a consumer expecting
   `unit` to be populated will read empty. Observed, not altered.
3. **The inference runtime is uninitialised under `ASGITransport`.** Not a
   production defect on its face — lifespan runs in a real server — but it means
   no in-process test can currently exercise the inference branch without
   explicitly calling `init_inference_runtime()`.

---

## Command Log

Commands **I executed**, with real outcomes:

```
$ ls /Users/sarasa/Documents/MVP_previsit/backend/tests/
    → LANDED. 60-file test inventory.

$ cd backend && grep -n "extract_text_from_pdf" -A 22 app/services/file_processor.py
    → LANDED. Confirmed pypdf PdfReader is the text-layer reader.

$ cd backend && python3 -m pytest tests/test_workspace_labs_e2e.py -q -s
    → 2 passed in 1.81s   (full evidence above)
```

Executed by the user and reported into this session:

```
$ cd backend && python3 -m pytest tests/test_clinical_context_document_only.py -q
2 passed in 1.36s
```

Blocked on every attempt (~25 across `Bash`, `Monitor`, `mcp__ide__executeCode`),
still to run:

```
cd backend && python3 -m pytest -q                       # full regression sweep
grep -rn "/clinician/" frontend --include='*.tsx' --include='*.ts' | grep -v node_modules
grep -rn "ClinicianDashboard" frontend --include='*.tsx' --include='*.ts' | grep -v node_modules
cd frontend && npm test && npm run test:e2e              # browser layer
```

---

## Remaining UNKNOWNs

1. Browser rendering of the Workspace shell and Labs card.
2. Runtime traversal of the repaired doctor route in a browser.
3. Repo-wide `/clinician/` grep — a stray non-canonical link cannot be excluded.
4. Full backend regression sweep after the two repairs.
5. Frontend unit tests after the route change.
6. Whether the inference branch initialises correctly under a real uvicorn boot
   (harness cannot answer this).
7. Persian label `میزکار بالینی` — awaiting native-speaker review.
8. Tesseract-based OCR quality on a *scanned* document — the confirmed path used
   a text layer, so image OCR accuracy remains unmeasured.

---

## Recommended Next Step

1. `cd backend && python3 -m pytest -q` — regression sweep for the two repairs.
2. The two frontend greps, to close UNKNOWN #3.
3. Browser layer: boot backend + frontend, walk `/` → `/doctor-login` →
   `/doctor-dashboard` → patient → `/clinician/{id}/workspace`, and screenshot the
   labs card. This is the only remaining acceptance gap.
4. Review the trust-provenance finding (#1 above) as its own diff.
5. Inference remains a separate workstream; do not couple it to labs visibility.

Verdict: `CONDITIONAL GO` — backend clinical path confirmed end-to-end; browser
layer outstanding.
