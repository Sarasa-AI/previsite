# Doctor Clinical Workflow Specification

- **Status:** Canonical (workflow behavior source of truth)
- **Date:** 2026-08-04
- **Audience:** Backend, frontend, product, QA, architecture
- **Related:**
  - [Doctor Workspace Orchestration](doctor-workspace-orchestration.md)
  - [Doctor Workspace API Contract](doctor-workspace-api-contract.md)
  - [Doctor Workspace Presentation Contract](doctor-workspace-presentation.md)
  - [Doctor Workspace Architecture Gate](doctor-workspace-architecture-gate.md)
  - [ADR 0001: Clinical Artifacts Aggregate](../adr/0001-clinical-artifacts-aggregate.md)
  - [MIGRATION.md](../../MIGRATION.md)

---

## 0. Purpose and non-goals

This document defines **Doctor Clinical Workflow behavior** for PreVisit. It transforms Doctor Workspace from a passive viewer into an interactive clinical workspace where the physician can acknowledge findings, review the decision queue, refresh the clinical story, manage workflow state, and prepare for future AI-assisted decision support.

This document is the **single source of truth for workflow behavior**. Orchestration, API wire shapes, presentation ViewModels, and the Architecture Gate remain locked unless this document explicitly authorizes an additive future endpoint behavior under the existing path prefix.

### What this document is NOT

| Out of scope | Rationale |
|--------------|-----------|
| UI redesign | Presentation chrome and layout stay locked |
| Architecture refactor | Clinical spine and Gate 1.0 remain locked |
| AI reasoning / DDx / recommendations | Generation is a separate concern; not this sprint |
| SSE / WebSocket / streaming | Polling or explicit refresh only |
| Mobile | Desktop clinician workspace only |
| Production code in this sprint | Specification only |

### Locked surfaces (must not change)

| Surface | Rule |
|---------|------|
| `ClinicalContext` | Immutable source aggregate; never mutated by workflow |
| `ClinicalContentResponse` | Content projection contract unchanged |
| `WorkspacePlan` (domain shape) | Computed snapshot only; never workflow truth; never mutated in place |
| `WorkspacePlanResponse` / DTO field shapes | Wire contract unchanged |
| `WorkspaceViewModel` | Presentation ViewModel shape unchanged |
| Registry / `CardPresenterProps` | Unchanged |
| `WorkspaceShell` layout | Composition only; unchanged |
| Presenters / card props | Stateless / presentational; unchanged |
| Projection mappers | Unchanged |
| Architecture Gate 1.0 proofs | Unchanged |

Workflow introduces **persistence and mutation behavior** outside these surfaces. Future endpoint behaviors under `/api/sessions/{session_id}/workspace/...` are specified here additively; they do not rewrite the locked API contract file in this sprint.

---

## 1. Principles

### 1.1 WorkspacePlan remains pure

`WorkspacePlan` is always a **computed snapshot**.

- It is never the source of workflow truth.
- Doctor interactions never mutate `WorkspacePlan` directly.
- Workflow persistence lives outside the plan.
- The next `WorkspaceOrchestrator.compute(...)` call generates a new `WorkspacePlan`.

### 1.2 Workflow Event Store is the source of truth

Every doctor action appends an immutable event to the **Workflow Event Store**. Folded workflow state drives the next compute. Audit is observational only.

```
Doctor Action
        │
        ▼
Workflow Event Store          ← canonical workflow persistence
        │
        ├────────────► Audit Log (append-only, observational)
        │
        ▼
ReviewAcknowledgements / SessionState
        │
        ▼
WorkspaceOrchestrator.compute()
        │
        ▼
WorkspacePlan (snapshot)
```

| Store | Role | Replay to reconstruct workflow? |
|-------|------|----------------------------------|
| **Workflow Event Store** | Canonical workflow persistence | **Yes** — fold events → review/session state |
| **AuditLog** | Observational security/compliance trail | **Never** |
| **WorkspacePlan** | Computed snapshot only | N/A — never persisted as truth |

Rules:

1. Workflow Event Store is the canonical workflow persistence.
2. AuditLog is observational only.
3. AuditLog must never be replayed to reconstruct workflow state.
4. Workflow state is reconstructed only from folded workflow events.
5. `WorkspacePlan` is always computed from folded workflow state + `ClinicalContext` + orchestration inputs.

### 1.3 Mapping table is mandatory

Business workflow vocabulary maps to locked `WorkspaceState` wire values only through the **explicit mapping table in §2**. No implicit mapping is permitted.

### 1.4 Origin-agnostic workflow

Workflow never depends on finding origin.

Finding sources may include:

- Rule Engine
- AI Runtime
- Knowledge Base
- Manual clinician findings
- Future plugins / products

All findings enter the identical lifecycle:

```
NEW → VIEWED → ACKNOWLEDGED → RESOLVED
                          └→ DISMISSED
```

| Concern | Owns |
|---------|------|
| **Generation** | WHAT appears (candidates, text, evidence refs) |
| **Workflow** | HOW clinicians interact (lifecycle, ack, resolve, dismiss) |

No workflow logic may branch based on whether a finding originated from AI, rules, or any future engine. Generation and interaction remain separate concerns.

### 1.5 Idempotency, concurrency, offline

- Mutations are idempotent for duplicate clinician actions on the same finding under the same `context_hash`.
- Optimistic concurrency uses `If-Match: {plan_etag}` on mutating endpoints.
- Offline clients may queue mutations locally and retry when connectivity returns; retries must re-read etag and apply §7 / §9 failure rules.

---

## 2. Business ↔ WorkspaceState mapping table (canonical)

Business workflow states use `UPPER_SNAKE`. Locked wire `WorkspaceState` values remain lowercase snake_case. This table is the **only** allowed translation layer.

| Business Workflow State | WorkspaceState (wire) | Visibility / UI mode | Allowed Actions | Terminal? |
|-------------------------|----------------------|----------------------|-----------------|-----------|
| — (operational) | `loading` | Skeleton / empty plan; poll only | None (poll GET only) | No |
| — (operational) | `generating` | Partial plan; SOAP may be badge | Poll; ack allowed only if plan emits `acknowledge_required` | No |
| `READY` | `verified` or `partially_verified` | Interactive; no open P0 gates | View chrome; story refresh if stale; resolve/dismiss non-gate items per queue; open docs/timeline/evidence/explanation | No |
| `REVIEWING` | `review_needed` or `conflict_present` with **zero** acknowledgements recorded for current open P0 set | Interactive review | Acknowledge P0; view; resolve/dismiss per rules; story refresh if allowed | No |
| `PARTIALLY_REVIEWED` | `review_needed` or `conflict_present` with **some but not all** required P0 acknowledgements recorded | Interactive partial review | Same as REVIEWING for remaining gates | No |
| `REVIEWED` | `completed` | Interactive complete; queue gates cleared | View; story refresh if stale; no further required acks | No |
| `CLOSED` | `read_only` after clinician close **or** session lock | Frozen plan | View only; all mutations rejected | **Yes** |
| — (operational) | `offline` | Frozen last plan | Poll / reconnect only; no mutations | No |
| — (operational) | `read_only` while `session_locked` without clinician CLOSE event | Frozen plan | View only | No (until unlock) or Yes if close confirmed |

### 2.1 Derivation rules

Business state is **derived**, never stored as a competing wire enum:

1. Fold Workflow Event Store → `ReviewAcknowledgements` + session close/lock signals.
2. Run `compute()` → obtain locked `workspace_state`.
3. Apply this table to derive business state for product/telemetry/UI labels.
4. Presentation continues to key off wire `workspace_state` and existing `WorkspaceUiState`; business labels are additive overlays, not replacements of locked UI state machines.

### 2.2 Allowed-action matrix (summary)

| Action | READY | REVIEWING | PARTIALLY_REVIEWED | REVIEWED | CLOSED | loading / generating / offline / read_only |
|--------|-------|-----------|--------------------|----------|--------|--------------------------------------------|
| Acknowledge P0 | No* | Yes | Yes | No* | No | generating: only if gate emitted; else No |
| Resolve item | Yes† | Yes† | Yes† | Yes† | No | No |
| Dismiss item | Yes† | Yes† | Yes† | Yes† | No | No |
| Refresh story | Yes if stale/allowed | Yes if allowed | Yes if allowed | Yes if allowed | No | No |
| View / expand / open source | Yes | Yes | Yes | Yes | Yes (view) | loading: No; others: view if plan present |

\* Unless a new P0 appears after context change (state returns to REVIEWING).  
† Subject to item lifecycle preconditions in §4 and §6.

---

## 3. Session lifecycle

### 3.1 States

```
READY
  ↓
REVIEWING
  ↓
PARTIALLY_REVIEWED
  ↓
REVIEWED
  ↓
CLOSED
```

Operational wire states (`loading`, `generating`, `offline`, `read_only`) may interrupt or precede this path; they are not renamed.

### 3.2 Transitions

| From | To | Trigger | Preconditions | Side effects | Failure |
|------|-----|---------|---------------|--------------|---------|
| (none) / loading→ready wire | `READY` | Plan available; no open P0 ack gates; not completed | Context available; not locked/offline | `WorkspaceOpened` workflow event (once per session open window) | Compute failure → 500; no plan |
| `READY` | `REVIEWING` | Open P0 / `acknowledge_required` appears | Mutations allowed | None beyond next compute | Stale etag on concurrent mutate → 409 |
| `REVIEWING` | `PARTIALLY_REVIEWED` | First required ack recorded while others remain | Object acknowledgeable | Fold ack into review state; recompute | Duplicate ack → idempotent success |
| `PARTIALLY_REVIEWED` | `REVIEWING` | New P0 appears (context change) while incomplete | Meaningful context change | Prior acks for unchanged objects retained per §4.5 | — |
| `PARTIALLY_REVIEWED` | `REVIEWED` | All required P0 ack'd; queue completion + SOAP accepted when applicable | Matches orchestration completion rules | Fold completion signals; recompute → `completed` | Incomplete SOAP acceptance → stay PARTIALLY_REVIEWED / REVIEWING |
| `READY` | `REVIEWED` | Direct completion path when gates already clear and SOAP accepted | Same as orchestration `completed` | Recompute | — |
| `REVIEWED` | `CLOSED` | Clinician closes session **or** session lock | Authored close event or `session_locked` | Workflow event `SessionClosed` / lock signal; mutations disabled | Close while refresh GENERATING → reject or wait per §5 |
| `CLOSED` | — | Terminal | — | — | Unlock/reopen is out of band (session admin); if unlocked, re-enter via compute |

### 3.3 Failure and retry

- Session transitions are **recomputed**, not client-asserted. Clients never POST a business state.
- After transient 500, retry GET workspace; identical folded state + context yields deterministic plan.
- Offline: retain last plan; set `offline=true` on GET; no mutations until reconnect.

---

## 4. Decision queue item lifecycle

### 4.1 States

```
NEW
  ↓
VIEWED
  ↓
ACKNOWLEDGED
  ↓
RESOLVED
  or
DISMISSED
```

Notes:

- `ACKNOWLEDGED` applies when the item carried `acknowledge_required` (P0 gate). Non-gate items may move `NEW → VIEWED → RESOLVED|DISMISSED` without an acknowledgement step.
- Ordering, priority, and queue membership remain **orchestrator-owned**. Workflow never reorders the queue.
- Queue items in the plan remain DTOs with existing fields only (`rank`, `object_id`, `reason_code`, `explanation`, `acknowledge_required`). Lifecycle phase is **not** a plan field; it is reconstructed from the Workflow Event Store when folding review state and interpreting the next snapshot.

### 4.2 Resolve vs Dismiss (formal)

#### RESOLVED

**Definition:** The clinician has completed review of the finding and considers it **clinically addressed**.

**Behavior:**

- Contributes to review completion.
- Not shown again in the active decision queue while `context_hash` is unchanged.
- May reappear as `NEW` only after a meaningful `ClinicalContext` change (new `context_hash` that reintroduces the finding as clinically relevant).
- Never deleted from history (Workflow Event Store retains `QueueItemResolved`).

Resolve is **not** a visibility reason. It removes the item from active review via folded `resolved_objects` consumed by the next `compute()`.

#### DISMISSED

**Definition:** The clinician intentionally **hides** the finding for the current clinical context.

Dismiss is **NOT** a clinical resolution. Dismiss is a **visibility decision only**.

**Behavior:**

- Maps to locked `VisibilityReason.physician_dismissed` on the next computed plan for that object (when the orchestrator hides it).
- Remains fully auditable (Workflow Event Store + mirrored AuditLog).
- Never deletes the finding.
- May reappear after `context_hash` changes.
- Does **not** imply the finding was clinically addressed.
- Does **not** alone satisfy P0 acknowledgement gates; a P0 that requires acknowledgement must still be acknowledged (or resolved under §6 rules) before queue advancement past its gate.

### 4.3 Ordering, priority, visibility

| Concern | Owner | Rule |
|---------|-------|------|
| Ordering | Orchestrator | Contiguous ranks 1..N; client must not reorder |
| Priority | Orchestrator | `p0`–`p3`; UI must not override |
| Active visibility | Orchestrator + folded dismiss/resolve sets | Dismissed → prefer hide with `physician_dismissed`; Resolved → omit from active queue while context unchanged |
| Resolved items | Workflow history | Visible in history/audit; not active queue |
| Dismissed items | Workflow history | Auditable; hidden in plan via visibility reason |

### 4.4 Re-open behavior

A finding may re-enter as `NEW` when:

1. `context_hash` changes and the orchestrator again emits the object into a visible non-hidden slot / queue, **or**
2. Orchestration explicitly re-pins a new P0 regardless of prior acknowledgement (orchestration safety rule).

Prior `RESOLVED` / `DISMISSED` / `ACKNOWLEDGED` events remain in history. Folding scopes active suppressions to the `context_hash` (or acknowledgement epoch) under which they were recorded. After a meaningful context change, suppressions for that object are cleared for active presentation unless a new dismiss/resolve is recorded.

### 4.5 Folded review state (conceptual — spec only)

Implementation will fold Workflow Event Store events into review inputs consumed by `compute()`. Conceptual sets (do **not** change production models in this documentation sprint):

| Folded field | Meaning |
|--------------|---------|
| `viewed_objects` | Objects that received `QueueItemViewed` under current context epoch |
| `acknowledged_objects` | Objects that received `QueueItemAcknowledged` (existing orchestration input) |
| `resolved_objects` | Objects clinically addressed (`QueueItemResolved`) |
| `dismissed_objects` | Objects hidden (`QueueItemDismissed`) → drives `physician_dismissed` |
| `story_refresh_requested` / story status | Story lifecycle (§5) |
| `session_closed` / lock signals | Session CLOSED / read_only |

Existing production `ReviewAcknowledgements` today exposes `acknowledged_objects`, `story_refresh_requested`, `story_frozen`. Extended fields are specified here for the implementation sprint; **WorkspacePlan / DTO shapes stay unchanged**.

---

## 5. Story refresh lifecycle

### 5.1 States

```
READY
  ↓
REFRESH_REQUESTED
  ↓
GENERATING
  ↓
READY
```

Failure branch: `GENERATING → READY` with stale/error signal and `StoryRefreshFailed` event.

### 5.2 Phases

| Phase | Meaning | Client behavior |
|-------|---------|-----------------|
| Refresh request | Clinician requests regeneration | `POST .../story/refresh` with `If-Match` |
| Refresh pending | Event stored; generation not finished | Poll `GET .../story/status` (and/or GET plan); no SSE |
| Refresh completed | New story in next plan snapshot | Full-replace ViewModel from plan `200` |
| Refresh failed | Generation failed | Plan may keep prior story + stale; surface error; allow retry |

### 5.3 Rules

- No streaming. No SSE. No WebSocket.
- Polling or explicit refresh only.
- Story text remains orchestrator-/story-engine-owned; workflow only records request/status and feeds `ReviewAcknowledgements` flags into the next compute.
- Physician edits to source facts (when applicable) freeze story and require explicit refresh (orchestration §7.8); workflow records the freeze/refresh events without mutating `ClinicalContext` here.

### 5.4 Transitions

| From | To | Trigger | Side effects | Failure |
|------|-----|---------|--------------|---------|
| READY | REFRESH_REQUESTED | Valid refresh POST | Append `StoryRefreshRequested`; set refresh flag | 409 stale/read_only; 403 |
| REFRESH_REQUESTED | GENERATING | Worker/engine accepted job | Status `generating` | Engine reject → FAILED path |
| GENERATING | READY | Generation success | Append `StoryRefreshCompleted`; clear flags; compute new plan with fresh story | Timeout/engine error → FAILED |
| GENERATING | READY (failed) | Generation failure | Append `StoryRefreshFailed`; story may remain stale | Client may retry POST |

---

## 6. Doctor actions

Every action defines: trigger, preconditions, state transition, side effects, workflow event, audit mirror, failure behavior.

### 6.1 Acknowledge

| Field | Spec |
|-------|------|
| **Trigger** | Clinician activates Acknowledge on an object with `acknowledge_required` |
| **Preconditions** | Mutations allowed; object in current plan queue/directives as P0 gate; `If-Match` matches; session not CLOSED/read_only/offline |
| **State transition** | Item: `VIEWED|NEW → ACKNOWLEDGED`. Session: REVIEWING → PARTIALLY_REVIEWED or PARTIALLY_REVIEWED → REVIEWED when last gate clears |
| **Side effects** | Append workflow event; fold into `acknowledged_objects`; claim session; `compute()`; return new plan |
| **Workflow event** | `QueueItemAcknowledged` |
| **Audit mirror** | `queue_item_acknowledged` (observational) |
| **Failure** | `409 WORKSPACE_PLAN_STALE` → refetch + retry; `409 WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE`; `409 WORKSPACE_READ_ONLY`; `422 WORKSPACE_OBJECT_UNKNOWN`; `403` access denied |

### 6.2 Refresh Story

| Field | Spec |
|-------|------|
| **Trigger** | Clinician activates Refresh when story present and stale (or explicit refresh allowed) |
| **Preconditions** | Mutations allowed; not CLOSED/read_only/offline; valid `If-Match` |
| **State transition** | Story: READY → REFRESH_REQUESTED → GENERATING → READY |
| **Side effects** | Append `StoryRefreshRequested`; run/queue generation; on completion append Completed/Failed; recompute plan |
| **Workflow event** | `StoryRefreshRequested` (+ `StoryRefreshCompleted` / `StoryRefreshFailed`) |
| **Audit mirror** | `story_refresh_requested` / `story_refresh_completed` / `story_refresh_failed` |
| **Failure** | 409 stale/read_only; on generation failure return READY+stale and allow retry; no SSE |

### 6.3 Resolve Queue Item

| Field | Spec |
|-------|------|
| **Trigger** | Clinician activates Resolve on a queue finding |
| **Preconditions** | Mutations allowed; object currently active in queue or visible directive; not already RESOLVED under current context epoch; valid `If-Match` |
| **State transition** | Item → `RESOLVED`. May contribute to session REVIEWED when completion rules met |
| **Side effects** | Append `QueueItemResolved`; fold `resolved_objects`; recompute (item omitted from active queue while context unchanged) |
| **Workflow event** | `QueueItemResolved` |
| **Audit mirror** | `queue_item_resolved` |
| **Failure** | 409 stale/read_only; 409 if object not resolvable in current plan; 422 unknown object; duplicate resolve → idempotent success |

### 6.4 Dismiss Queue Item

| Field | Spec |
|-------|------|
| **Trigger** | Clinician activates Dismiss (hide) on a finding |
| **Preconditions** | Mutations allowed; object visible; valid `If-Match`; not CLOSED |
| **State transition** | Item → `DISMISSED` (visibility only; not clinical completion) |
| **Side effects** | Append `QueueItemDismissed`; fold `dismissed_objects`; next plan hides via `VisibilityReason.physician_dismissed` |
| **Workflow event** | `QueueItemDismissed` |
| **Audit mirror** | `queue_item_dismissed` |
| **Failure** | 409 stale/read_only; duplicate dismiss → idempotent success; dismiss does not clear P0 ack gates |

### 6.5 Open Source Document

| Field | Spec |
|-------|------|
| **Trigger** | Clinician opens a source document from documents card / evidence link |
| **Preconditions** | Plan present; document ref exists in content |
| **State transition** | None to session/queue lifecycle (view-only) |
| **Side effects** | Append workflow event; optional local chrome |
| **Workflow event** | `SourceDocumentOpened` |
| **Audit mirror** | `source_document_opened` |
| **Failure** | Missing doc → UI empty/error state; no plan mutation |

### 6.6 Expand Timeline

| Field | Spec |
|-------|------|
| **Trigger** | Clinician expands timeline chrome |
| **Preconditions** | Timeline card present |
| **State transition** | None (local focus expand may clear on plan replace) |
| **Side effects** | Append workflow event; local UI expand only — never POST layout |
| **Workflow event** | `TimelineExpanded` |
| **Audit mirror** | `timeline_expanded` |
| **Failure** | N/A (local); telemetry on unknown object skip remains presentation rule |

### 6.7 View Evidence

| Field | Spec |
|-------|------|
| **Trigger** | Clinician opens evidence refs for a finding/story |
| **Preconditions** | Evidence refs present |
| **State transition** | None required; may coincide with VIEWED if first view of queue item |
| **Side effects** | Append `EvidenceViewed`; if first queue focus, also `QueueItemViewed` |
| **Workflow event** | `EvidenceViewed` |
| **Audit mirror** | `evidence_viewed` |
| **Failure** | Missing evidence → empty state |

### 6.8 View Explanation

| Field | Spec |
|-------|------|
| **Trigger** | Clinician opens queue/item explanation / visibility reason chrome |
| **Preconditions** | Explanation present on queue item or directive |
| **State transition** | None (explainability is write-only from orchestration; never feeds back into compute as input reasoning) |
| **Side effects** | Append `ExplanationViewed` |
| **Workflow event** | `ExplanationViewed` |
| **Audit mirror** | `explanation_viewed` |
| **Failure** | N/A |

---

## 7. Acknowledgement rules

### 7.1 What can be acknowledged

- Objects currently emitted with `acknowledge_required` (P0 gate) in the active plan.
- Typically safety-critical queue objects per orchestration (conflicts, allergies, red flags, critical labs, etc.).

### 7.2 What cannot be acknowledged

- Objects without `acknowledge_required`.
- Hidden objects.
- Objects unknown to the catalog (`422 WORKSPACE_OBJECT_UNKNOWN`).
- Any mutation when `read_only`, `offline`, or CLOSED.
- Client-invented object ids not in the current plan.

### 7.3 Duplicates and idempotency

- Re-acknowledging an already acknowledged object under the same context epoch returns **success** with the current (recomputed) plan.
- No duplicate `acknowledged_objects` membership; fold is set-valued.
- Prefer a single `QueueItemAcknowledged` event per object per context epoch; duplicate POSTs may append an idempotent no-op marker or skip append while still returning 200 — implementation must guarantee fold state unchanged and plan deterministic.

### 7.4 Offline retry

1. Client queues the intent locally while offline.
2. On reconnect, GET workspace (fresh etag).
3. If object still acknowledgeable, POST with new `If-Match`.
4. If object no longer acknowledgeable (gate cleared or context changed), drop intent and refresh UI from plan.
5. Never apply optimistic plan patches.

### 7.5 Error handling

| Code | HTTP | Behavior |
|------|------|----------|
| `WORKSPACE_PLAN_STALE` | 409 | Refetch plan; full-replace; retry if still applicable |
| `WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE` | 409 | Refetch; do not retry same intent blindly |
| `WORKSPACE_READ_ONLY` | 409 | Disable mutations; show read-only chrome |
| `WORKSPACE_OBJECT_UNKNOWN` | 422 | Client bug / stale catalog; refetch |
| `WORKSPACE_ACCESS_DENIED` | 403 | Blocking error |
| `WORKSPACE_COMPUTE_FAILED` | 500 | Retry GET later; no partial plan |

### 7.6 Audit trail

Every acknowledgement persists `QueueItemAcknowledged` in the Workflow Event Store and mirrors observationally to AuditLog. Reconstruction uses the Event Store only.

---

## 8. Workflow events and AuditLog mirror

### 8.1 Canonical workflow events

| Event | When |
|-------|------|
| `WorkspaceOpened` | First open / authorized GET workspace for session window |
| `CardViewed` | Card enters focused view |
| `TimelineExpanded` | Timeline expand chrome |
| `QueueItemViewed` | Queue item focused/opened |
| `QueueItemAcknowledged` | P0 acknowledgement recorded |
| `QueueItemResolved` | Clinical resolve recorded |
| `QueueItemDismissed` | Visibility dismiss recorded |
| `StoryRefreshRequested` | Refresh POST accepted |
| `StoryRefreshCompleted` | Generation succeeded |
| `StoryRefreshFailed` | Generation failed |
| `SourceDocumentOpened` | Source document opened |
| `EvidenceViewed` | Evidence inspected |
| `ExplanationViewed` | Explanation inspected |
| `SessionClosed` | Clinician close (when product exposes close) |

Events are immutable, append-only, ordered, and scoped by `session_id` (+ actor user id). Payloads must avoid free-text PHI; use ids, object_ids, etags, context_hash, and reason codes.

### 8.2 AuditLog mirror

Each workflow mutation also appends an observational `AuditLog` row via existing `record_audit` (snake_case `action`).

Rules:

1. AuditLog must never be used to reconstruct workflow state.
2. No PHI in audit free text.
3. **Fail-soft audit:** a failure to write AuditLog must not roll back a successfully persisted Workflow Event Store append. Document the transaction boundary as: workflow event commit first; audit best-effort second.
4. Existing obligation `view_workspace` on first GET/day remains compatible; map to / coexist with `WorkspaceOpened`.

---

## 9. API behavior (specify only — do not implement)

All paths under locked prefix:

`/api/sessions/{session_id}/workspace/`

Auth: Doctor, Admin (patients `403`). Mutations: `claim=True`. Optimistic concurrency: `If-Match: {plan_etag}` required on POSTs.

Successful mutations: **append workflow event → fold state → `compute()` → return full-replaced `WorkspacePlanResponse`**. Never return a patched plan.

### 9.1 `POST /api/sessions/{session_id}/workspace/acknowledgements`

Already defined in the API contract; behavior deepened here.

**Request**

```json
{ "object_id": "conflicts" }
```

Headers: `Authorization`, `If-Match`.

Optional: `Idempotency-Key` (recommended for offline retry).

**Response:** `200` + `WorkspacePlanResponse` + new `ETag`.

**Errors:** `409 WORKSPACE_PLAN_STALE` | `409 WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE` | `409 WORKSPACE_READ_ONLY` | `422 WORKSPACE_OBJECT_UNKNOWN` | `403 WORKSPACE_ACCESS_DENIED` | `500 WORKSPACE_COMPUTE_FAILED`

**Idempotency:** Duplicate ack for same object/context epoch → `200` with current plan.

### 9.2 `POST /api/sessions/{session_id}/workspace/decision-items/{object_id}/resolve`

**Request body:** `{}` or `{ "note_code": "addressed" }` (no free-text PHI).

Headers: `Authorization`, `If-Match`. Optional `Idempotency-Key`.

**Response:** `200` + full `WorkspacePlanResponse`.

**Semantics:** Clinical resolve (§4.2). Does not set `physician_dismissed`.

**Errors:** `409 WORKSPACE_PLAN_STALE` | `409 WORKSPACE_READ_ONLY` | `409 WORKSPACE_OBJECT_NOT_RESOLVABLE` (object not active / not allowed) | `422 WORKSPACE_OBJECT_UNKNOWN` | `403` | `500`

**Idempotency:** Duplicate resolve → `200`.

### 9.3 `POST /api/sessions/{session_id}/workspace/decision-items/{object_id}/dismiss`

**Request body:** `{}`.

Headers: `Authorization`, `If-Match`. Optional `Idempotency-Key`.

**Response:** `200` + full `WorkspacePlanResponse` (object typically `hidden` with `visibility_reason: physician_dismissed`).

**Semantics:** Visibility only (§4.2). Does not imply clinical resolution. Does not satisfy acknowledgement gates by itself.

**Errors:** `409 WORKSPACE_PLAN_STALE` | `409 WORKSPACE_READ_ONLY` | `409 WORKSPACE_OBJECT_NOT_DISMISSIBLE` | `422 WORKSPACE_OBJECT_UNKNOWN` | `403` | `500`

**Idempotency:** Duplicate dismiss → `200`.

### 9.4 `POST /api/sessions/{session_id}/workspace/story/refresh`

Already defined in the API contract; behavior deepened here.

**Request:** `{}` + `If-Match`.

**Responses:**

| Status | When |
|--------|------|
| `200` | Refresh completed synchronously; body is new `WorkspacePlanResponse` |
| `202` | Refresh accepted; story status `generating`; body may include `{ "story_status": "generating" }` and/or current plan; client polls §9.5 then GET workspace |

**Errors:** `409 WORKSPACE_PLAN_STALE` | `409 WORKSPACE_READ_ONLY` | `403` | `500`

No SSE.

### 9.5 `GET /api/sessions/{session_id}/workspace/story/status`

**Response `200`:**

```json
{
  "story_status": "ready | refresh_requested | generating | failed",
  "context_hash": "<hash>",
  "stale": false,
  "plan_etag": "<etag-or-null>"
}
```

**Errors:** `403` | `404` if workspace unavailable.

**Client:** Poll while `generating` / `refresh_requested`; when `ready` or `failed`, GET `/workspace` for full replace. No streaming.

### 9.6 Shared mutation algorithm

```
1. Authorize + claim session
2. Validate If-Match against current plan_etag
3. Validate preconditions for action
4. Append immutable Workflow Event Store event
5. Fold events → ReviewAcknowledgements / SessionState
6. Best-effort AuditLog mirror (fail-soft)
7. WorkspaceOrchestrator.compute(...)
8. Map to WorkspacePlanResponse; return 200 + ETag
```

Never mutate queue items in place on a stored plan. Never write workflow truth into AuditLog-only storage.

---

## 10. Frontend behavior

### 10.1 Layer rules

| Layer | Responsibility |
|-------|----------------|
| `WorkspaceShell` | Composition only |
| Presenters / cards | Stateless, presentational |
| Components | Presentational |
| Hooks (`useWorkspacePlan`, etc.) | Own interaction / mutations |
| UI state machine (`workspaceUiState`) | Local UI modes from wire state |
| Business mapping | Dedicated mapper from wire → business labels via §2 table (spec’d; implement later) |
| API client / service | Transport only; no clinical reasoning |

**No component talks directly to APIs.**

### 10.2 Interaction rules

1. Enable mutation CTAs only when `mutationsAllowed` and §2 / §6 preconditions hold.
2. Acknowledge, Resolve, and Dismiss are **distinct** CTAs with distinct preconditions and copy.
3. On mutation `200`: **full-replace** ViewModel from body + new etag (no merge).
4. On `202` story refresh: enter refreshing UI; poll `story/status`; then GET plan full-replace.
5. On `409 WORKSPACE_PLAN_STALE`: refetch; full-replace; optionally retry.
6. Local focus expand (timeline) never POSTs layout; cleared on plan replace.
7. Unknown `object_id`: skip + telemetry; never speculative render.

### 10.3 Offline

Queue intents in the hook/service layer; flush per §7.4. Do not invent plan patches offline.

---

## 11. Backend responsibilities

| Responsibility | Detail |
|----------------|--------|
| Transport / auth / claim / ETag | Existing session RBAC + contract headers |
| Workflow Event Store | Persist immutable events; sole reconstruction source |
| Fold | Derive `ReviewAcknowledgements` / `SessionState` inputs |
| Compute | Call pure `WorkspaceOrchestrator.compute` |
| Dismiss bridge | Feed dismissed set so layout may emit `visibility_reason: physician_dismissed` |
| Audit mirror | Best-effort `record_audit`; never replay for workflow |
| Purity | Never mutate `WorkspacePlan` in place; never mutate `ClinicalContext` |
| Errors | Envelope codes per §9; no PHI |
| Origin agnosticism | Accept findings from any generator into the same lifecycle |

---

## 12. Architecture boundaries

### 12.1 Must not change

- `ClinicalContext`
- `ClinicalContentResponse`
- `WorkspacePlan` domain field shapes
- `WorkspaceViewModel` / registry / shell layout / presenters / card props
- Projection contracts
- Architecture Gate 1.0 locked proofs
- Existing GET workspace / clinical-content / trace response shapes

### 12.2 Additive (implementation sprint later)

- Workflow Event Store persistence
- Folding of resolve/dismiss/viewed into orchestrator inputs
- POST resolve / dismiss and GET story/status handlers
- Deepened acknowledgement / story refresh handlers
- Frontend hook wiring for resolve/dismiss/status polling
- Business-state mapper overlay

### 12.3 Explicit non-goals

AI generation, differential diagnosis, recommendations, SSE, websockets, mobile, UI redesign, client-driven priority/layout/visibility.

---

## 13. Acceptance criteria

The specification completely defines:

- [x] Session lifecycle (`READY` → `CLOSED`) with operational wire states
- [x] Queue lifecycle (`NEW` → `RESOLVED` / `DISMISSED`)
- [x] Acknowledgement lifecycle, rules, idempotency, offline retry
- [x] Story refresh lifecycle without SSE
- [x] Workflow events as source of truth
- [x] AuditLog as observational mirror only
- [x] Failure states and retry behavior
- [x] Idempotency for ack / resolve / dismiss
- [x] API behavior for ack, resolve, dismiss, story refresh, story status
- [x] Frontend behavior (shell/presenters/hooks boundaries)
- [x] Backend responsibilities
- [x] State transitions
- [x] Architecture boundaries
- [x] Mandatory Business ↔ WorkspaceState mapping table
- [x] Formal Resolve vs Dismiss differentiation
- [x] `VisibilityReason.physician_dismissed` as dismiss visibility bridge
- [x] Origin-agnostic lifecycle
- [x] WorkspacePlan remains computed snapshot only

---

## 14. Architecture verification

| Check | Result |
|-------|--------|
| WorkspacePlan remains a computed snapshot | Pass — §1.1, §9.6 |
| Workflow persistence independent from AuditLog | Pass — §1.2, §8 |
| AuditLog never replayed for workflow | Pass — §1.2, §8.2 |
| Resolve and Dismiss formally differentiated | Pass — §4.2 |
| `VisibilityReason.physician_dismissed` is dismiss visibility bridge | Pass — §4.2, §9.3 |
| Workflow completely origin-agnostic | Pass — §1.4 |
| No WorkspacePlan / DTO / Presentation / ClinicalContext / Registry changes introduced | Pass — documentation only; §0 locked surfaces |
| No SSE | Pass — §5, §9.4–9.5 |

---

## 15. Sprint output

```
Created
Architecture verification
Ready for implementation
```
