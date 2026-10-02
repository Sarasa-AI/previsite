# Clinical Pipeline Notes (supersedes GapGPT migration doc)

## Canonical clinical spine

All patient entry modalities (intake, chat, uploads, future voice) must converge on:

```
modality adapters
  → Summary / Intake / MedicalOverview / Files
    → ClinicalContextBuilder.build
    → ClinicalContext                          # source clinical aggregate
    → TimelineBuilder.build
    → ClinicalContext.timeline                 # first derived artifact (additive; see ADR)
    → Clinical Intelligence (findings/risks/recommendations)  # peer derived artifact
    → WorkspaceOrchestrator.compute            # derived orchestration plan (see architecture spec)
         ↑ consumes findings via OrchestratorInputs adapter (not ClinicalContext)
    → WorkspacePlan                            # attention, priority, layout directives
    → GET /api/sessions/{session_id}/workspace # API contract (see API contract spec)
    → Presentation (DTO → ephemeral ViewModels; see presentation spec)
    → soap_generator (via soap_task only)
    → Summary.soap_* + Session.soap_status
```

`ClinicalTimeline` is the first derived clinical artifact. Clinical Intelligence findings
are a peer derived artifact persisted outside `ClinicalContext` and consumed by Workspace
only through adapter inputs (`OrchestratorInputs.clinical_findings`). `WorkspacePlan` is the
orchestration artifact that determines physician attention, priority, and layout behavior
without modifying `ClinicalContext`. See
[`docs/architecture/doctor-workspace-orchestration.md`](docs/architecture/doctor-workspace-orchestration.md)
for orchestration behavior,
[`docs/architecture/doctor-workspace-api-contract.md`](docs/architecture/doctor-workspace-api-contract.md)
for the API boundary, and
[`docs/architecture/doctor-workspace-presentation.md`](docs/architecture/doctor-workspace-presentation.md)
for the Presentation Contract (DTO → ViewModel renderer rules).

Do not stack further derived AI outputs (DDx, risk scores, recommendations, explainability) onto
`ClinicalContext` long-term;
see [`docs/adr/0001-clinical-artifacts-aggregate.md`](docs/adr/0001-clinical-artifacts-aggregate.md).

Document extraction uses Tesseract OCR (`ocr_service` + `drug_matcher`), not LLM vision analyzers.

## Removed dead modules (pipeline audit)

- `backend/app/services/medical_file_analyzer.py` — unused LLM document analyzer
- `backend/app/services/medical_extractor.py` — unused free-text extractor
- Abandoned ad-hoc scripts (`test_gapgpt.py`, `test_openai_error.py`, `test_httpx_params.py`, `test_diagnostic_flow.py`, `openrouter-test.py`)

## Deprecated (kept for compatibility)

- `GET /api/pmh/schema` — returns 410; nested questionnaire replaced by MedicalOverview
- `POST /api/pmh/submit` — prefer intake Layer 4 / submit; overview write still works
- Legacy `PatientPMH.answers_json` read path in `ClinicalContextBuilder` / `pmh_service` helpers

## Observability

Clinical AI pipeline stages emit PHI-safe structured telemetry via
`app.core.observability` (`ClinicalPipelineEvent` / `AITelemetryEvent`),
correlation IDs (`X-Request-ID`), and in-process Prometheus metrics at `GET /metrics`.

## LLM providers

Primary path is OpenRouter via `llm_cascade` / `openrouter_service`. Provider-specific settings remain in `backend/app/core/config.py` and `.env.example`.
