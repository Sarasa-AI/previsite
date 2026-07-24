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
  → soap_generator (via soap_task only)
  → Summary.soap_* + Session.soap_status
```

`ClinicalTimeline` is the first derived clinical artifact. Do not stack further derived AI
outputs (DDx, risk scores, recommendations, explainability) onto `ClinicalContext` long-term;
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
