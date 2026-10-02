# ADR 0001: Clinical Artifacts Aggregate

- **Status:** Accepted (direction only — not implemented this sprint)
- **Date:** 2026-07-24

## Context

`ClinicalContext` is the source clinical aggregate: modality adapters assemble patient facts
(intake, chat, PMH/overview, labs, medications, OCR) into one immutable object.

The Clinical Timeline Engine introduces `ClinicalTimeline` as a **derived** clinical artifact
computed from `ClinicalContext`. For delivery speed this sprint attaches it additively as
`ClinicalContext.timeline`.

Without an explicit boundary, subsequent Clinical AI modules (Differential Diagnosis, Risk
Scores, Recommendations, Explainability, etc.) risk stacking more derived outputs onto
`ClinicalContext`, turning the source aggregate into a long-term dump of AI products.

## Decision

1. Treat `ClinicalTimeline` as the **first derived clinical artifact**.
2. Keep `ClinicalContext` as the **source** clinical aggregate for assembled patient facts.
3. Do **not** grow `ClinicalContext` into a long-term container of derived AI outputs.
4. Eventually group derived capabilities under a dedicated `ClinicalArtifacts` aggregate, e.g.:

   ```
   ClinicalArtifacts
     ├── timeline: ClinicalTimeline
     ├── workspace_plan: WorkspacePlan   # orchestration (see architecture spec)
     ├── differential_diagnosis: ...   # future
     ├── risk_scores: ...              # future
     ├── recommendations: ...          # future
     └── explainability: ...           # future
   ```

5. The Timeline Engine public contract must remain:

   ```
   TimelineBuilder.build(ClinicalContext) → ClinicalTimeline
   ```

   Moving attachment from `ClinicalContext.timeline` to `ClinicalArtifacts.timeline` must
   **not** require changes to the Timeline Engine itself — only the composition/orchestration
   layer that attaches the result.

## Consequences

- **This sprint:** additive `ClinicalContext.timeline` only; no `ClinicalArtifacts` type or package.
- **Future modules:** consume `ClinicalTimeline` (via context today, via artifacts later); never
  rebuild chronology independently.
- **Follow-up work:** introduce `ClinicalArtifacts`, migrate `timeline` off `ClinicalContext`,
  and leave `modules/timeline` unchanged aside from import sites at the attachment point.

## References

- `backend/app/modules/timeline/`
- `backend/app/schemas/clinical_context.py`
- `MIGRATION.md` (canonical clinical spine)
- [`docs/architecture/doctor-workspace-orchestration.md`](../architecture/doctor-workspace-orchestration.md) — `WorkspacePlan` orchestration specification
- [`docs/architecture/doctor-workspace-api-contract.md`](../architecture/doctor-workspace-api-contract.md) — `WorkspacePlan` API boundary and DTO contracts
