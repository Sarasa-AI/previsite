# Doctor Workspace Architecture Gate

- **Status:** Canonical (mandatory after every future sprint)
- **Architecture Gate Version:** 1.0
- **Date:** 2026-08-02
- **Audience:** Backend, frontend, QA, architecture review
- **Related:** [Doctor Workspace Orchestration](doctor-workspace-orchestration.md), [Doctor Workspace API Contract](doctor-workspace-api-contract.md), [Doctor Workspace Presentation Contract](doctor-workspace-presentation.md), [Doctor Clinical Workflow](doctor-clinical-workflow.md), [ADR 0001: Clinical Artifacts Aggregate](../adr/0001-clinical-artifacts-aggregate.md), [MIGRATION.md](../../MIGRATION.md)

---

## 1. Purpose

This document is the **Architecture Gate checklist** for the Doctor Workspace.

It verifies that every architectural boundary from `ClinicalContext` to the final rendered Workspace remains intact after a sprint.

This gate is **validation only**. Passing it does not authorize new features, UI redesign, workflow, API changes, or production contract edits.

### Versioning

```
Architecture Gate Version: 1.0
```

| Rule | Requirement |
|------|-------------|
| Increment | Future changes to validation rules **must increment** this version |
| Sprint reports | Sprint reports **must reference** the Architecture Gate version used during validation |
| Golden dataset | Intentional changes to the Golden Clinical Dataset that alter regression expectations require a gate version bump + changelog note below |

### Changelog

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-08-02 | Initial gate: field mapping, semantic invariants, golden dataset, boundary isolation |

---

## 2. Pipeline under proof

```
ClinicalContext
        ↓
WorkspacePlan
        ↓
WorkspacePlanResponse (DTO)
        ↓
projectPlan
        ↓
WorkspaceViewModel + ClinicalContentViewModel
        ↓
Registry
        ↓
WorkspaceShell
        ↓
Presenter
        ↓
Reusable Components
```

Validation covers two complementary layers:

1. **Field mapping** — nothing lost, duplicated, or renamed unexpectedly
2. **Semantic invariants** — meaning preserved (ordering, priority, visibility, trust, identity, narrative, card assignment)

---

## 3. Golden Clinical Dataset

**Golden Clinical Dataset** is an **architectural regression reference**. It is **NOT** a performance benchmark.

Future validation compares the rendered pipeline against this canonical dataset. The dataset must remain stable.

| Artifact | Path |
|----------|------|
| Fixture | `frontend/src/modules/workspace/tests/goldenClinicalDataset.ts` |
| Integrity tests | `frontend/src/modules/workspace/tests/goldenDatasetIntegrity.test.ts` |

---

## 4. Mandatory checklist

Run after every sprint. Mark Pass / Fail. Cite **Architecture Gate Version: 1.0** in the sprint report.

| # | Criterion | Proof | Pass/Fail |
|---|-----------|-------|-----------|
| 1 | Public APIs unchanged (backend interface, frontend component props) | Diff review; no production API edits in sprint | |
| 2 | Presentation contracts unchanged (`WorkspaceViewModel`, `CardPresenterProps`) | Diff review of `presentation/viewmodels/types.ts`, `registry/types.ts` | |
| 3 | Registry unchanged (16 IDs, presenter map, bands) | `frontend/.../tests/cardRegistry.test.ts` | |
| 4 | Mapper contracts unchanged (`to_workspace_plan_response`, `projectPlan`) | Diff review; `backend/tests/test_workspace_interface.py`, `projectPlan.test.ts` | |
| 5 | Workspace layout unchanged (Shell composition-only) | Diff review of `WorkspaceShell.tsx`; `architectureBoundaries.test.ts` | |
| 6 | Card interfaces unchanged | Diff review of component public props | |
| 7 | No forbidden imports | `frontend/.../tests/architectureBoundaries.test.ts` | |
| 8 | No new coupling (presentation ↔ backend/domain leakage) | `architectureBoundaries.test.ts`; backend mapper isolation tests | |
| 9 | Trust never in body content; trust chrome from plan | `goldenDatasetIntegrity.test.ts`; `presentationIntegration.test.tsx`; semantic trust tests | |
| 10 | Full-replace / no patch / no merge / no streaming | `etagReplacement.test.ts`; `workspaceCache.test.ts` | |
| 11 | Immutable ViewModels; presenters do not mutate props | `projectPlan.test.ts`; `semanticInvariants.test.ts`; `architectureBoundaries.test.ts` | |
| 12 | Contract completeness (field mapping) | `backend/tests/test_workspace_contract_validation.py`; `contractCompleteness.test.ts` | |
| 13 | Semantic invariants (ordering, priority, visibility, trust, identity, narrative, card assignment) | `test_workspace_contract_validation.py`; `semanticInvariants.test.ts`; golden Shell tests in `presentationIntegration.test.tsx` | |
| 14 | Golden Clinical Dataset integrity | `goldenDatasetIntegrity.test.ts` | |

---

## 5. Semantic invariants (detail)

| Invariant | Must prove |
|-----------|------------|
| Ordering | Clinical object / band / pin_zone / queue order identical across Plan → DTO → ViewModel → Shell regions |
| Priority | Priority values never change after mapping; presenters do not alter priority |
| Visibility | `visibility_reason` preserved; hidden stay hidden; deferred stay deferred; pinned stay pinned |
| Trust | Trust metadata identical; render only via presentation chrome; never inside body content |
| Identity | Object IDs unchanged; no duplicates; no missing catalog IDs |
| Narrative | Story / chief complaint / SOAP text not truncated, reordered, or silently modified by presentation |
| Card semantics | Each presenter renders exactly its assigned object slice |

---

## 6. Validated documentation assumptions

| Assumption | Status under Gate 1.0 |
|------------|------------------------|
| Presentation expects full replacement | Validated |
| No patching | Validated |
| No merge across ETags | Validated |
| No streaming / incremental apply in Presentation | Validated |
| Trust chrome is plan-owned | Validated |

Do not rewrite locked orchestration / API / presentation contracts when assumptions hold — record proof here and in tests only.

---

## 7. Known placeholders (not gate failures)

| Placeholder | Notes |
|-------------|-------|
| `ClinicalContentViewModel` wired in `WorkspaceRoute` via `GET .../clinical-content` | Resolved in Clinical Content Integration sprint — production path uses `useClinicalContent` + `projectClinicalContent`; fixtures remain test-only |
| POST acknowledgements / story refresh / decision actions | Specified in [Doctor Clinical Workflow](doctor-clinical-workflow.md); implementation pending |
| Full `OrchestratorInputs` / `SessionState` API adapter population | Out of scope for this gate |
| SSE / streaming | Explicit non-goal until a later transport sprint |

---

## 8. Verification commands

```bash
cd backend && python -m pytest tests/test_workspace_*.py -q
cd frontend && npx vitest run src/modules/workspace
```

Sprint reports must state:

> Architecture Gate Version: 1.0 — Pass | Fail
