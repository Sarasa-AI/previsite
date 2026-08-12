# OpenRouter Inference Adapter

**Status:** Production-ready infrastructure foundation  
**Version:** 1.0.0  
**Layer:** Inference Infrastructure / Provider

---

## Purpose

The OpenRouter inference adapter is the **first real provider implementation** of the inference runtime protocol. It enables structured clinical inference through the OpenRouter API while maintaining strict architectural boundaries and provider isolation.

This is **infrastructure only**. The adapter does not contain clinical reasoning logic, disease-specific rules, or product-specific business logic. It implements the neutral `InferenceAdapter` protocol and remains fully replaceable.

---

## Architecture

### Dependency Direction

```text
Inference Domain (protocol, models)
        ↑
Inference Application (pipeline, registry)
        ↑
Inference Infrastructure (providers)
        ↑
OpenRouter Provider (adapter, client, mapper)
        ↑
OpenRouter API
```

### Package Structure

```text
backend/app/core/inference/infrastructure/providers/openrouter/
├── __init__.py          # Public API surface
├── errors.py            # Provider-specific exceptions
├── models.py            # Provider-local wire models
├── client.py            # Async HTTP client
├── prompts.py           # Message construction
├── mapper.py            # Provider → domain boundary
└── adapter.py           # InferenceAdapter implementation
```

### Composition

```text
backend/app/core/inference/infrastructure/composition.py
```

Registration and factory functions live **outside** the provider package to maintain clean boundaries.

---

## Request Flow

```text
InferenceRequest
      ↓
InferencePipeline
      ↓
InferenceRegistry
      ↓
OpenRouterInferenceAdapter
      ↓
build_inference_messages()
      ↓
OpenRouterClient.complete()
      ↓
POST https://openrouter.ai/api/v1/chat/completions
      ↓
OpenRouterCompletionResponse
      ↓
parse structured JSON
      ↓
OpenRouterStructuredOutput (validate)
      ↓
map_structured_output_to_findings()
      ↓
tuple[InferenceFinding, ...]
      ↓
InferenceResult
```

---

## Provider Boundary

### OpenRouter Provider MUST NOT Import

* `app.modules.intelligence`
* `app.modules.workspace`
* `ClinicalFinding`
* `RiskSignal`
* `Recommendation`
* `WorkspacePlan`

### Provider Wire Models

Provider-local Pydantic models (`OpenRouterMessage`, `OpenRouterProviderFinding`, etc.) remain **strictly provider-local**. They must not be exposed to the domain or application layers.

### Mapper Boundary

`mapper.py` is the **only** file that crosses the provider/domain boundary:

```text
OpenRouterStructuredOutput
        ↓
map_structured_output_to_findings()
        ↓
tuple[InferenceFinding, ...]
```

All other provider modules must remain domain-agnostic.

---

## Configuration

### Settings

```python
# Required (must be set via environment)
OPENROUTER_API_KEY

# Optional (with defaults)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_INFERENCE_TIMEOUT = 30.0
OPENROUTER_HTTP_REFERER = "http://localhost:3000"
OPENROUTER_APP_TITLE = "PreVisit MVP"
```

### API Key Validation

The API key is validated at **composition time** using:

```python
is_openrouter_api_key_configured()
```

Empty, `None`, or placeholder keys are rejected immediately.

### Timeout

Use `OPENROUTER_INFERENCE_TIMEOUT` or `OPENROUTER_TIMEOUT` to configure the HTTP request timeout.

---

## Error Handling

### Provider Exception Hierarchy

```text
OpenRouterError
├── OpenRouterAuthError (401)
├── OpenRouterRateLimitError (429)
├── OpenRouterTimeoutError
├── OpenRouterTransportError
├── OpenRouterHTTPError (other 4xx/5xx)
├── OpenRouterResponseError (malformed API response)
└── OpenRouterStructuredOutputError (invalid model JSON)
```

### Rate Limiting

`OpenRouterRateLimitError` preserves the `Retry-After` header value when available:

```python
except OpenRouterRateLimitError as exc:
    retry_after_seconds = exc.retry_after
```

### Failure Semantics

Provider exceptions **propagate to the caller** according to the existing `InferencePipeline` contract. The adapter does not swallow or transform provider errors into `FAILED` status results.

---

## Structured Output

### Expected Schema

The model must return JSON matching:

```json
{
  "findings": [
    {
      "finding_key": "stable_unique_key",
      "artifact_type": "clinical_finding",
      "title": "Short title",
      "summary": "Concise summary",
      "confidence": 0.95,
      "attributes": {}
    }
  ]
}
```

### Validation

1. Parse `choices[0].message.content` as JSON
2. Validate with `OpenRouterStructuredOutput.model_validate()`
3. Map to `InferenceFinding` via `mapper.py`
4. Fail explicitly if validation fails

Empty findings (`{"findings": []}`) are valid.

Partial/silent mapping is forbidden. If a finding cannot be mapped, the entire inference fails.

---

## Security

### API Key Handling

The API key must **never** appear in:

* Logs
* Exception messages
* Runtime metadata
* Execution traces
* Test output

### No Secrets in Telemetry

`InferenceResult.runtime_metadata` contains only:

```python
{
    "provider": "openrouter",
    "model": "<model_id>",
    "base_url": "<base_url>",
}
```

Never include:

* API key
* Authorization header
* Request secrets
* Raw provider headers

---

## Context Reference Limitation

**IMPORTANT:** The current implementation treats `InferenceRequest.context_reference` as **opaque**.

Real clinical context resolution is **not part of this adapter** unless an external context-resolution port is added at the inference runtime level.

The prompt instructs the model to work with the opaque reference, but this is an **infrastructure smoke path only**. Do not claim that the system performs real clinical inference until a real clinical-context input mechanism exists.

---

## Testing Strategy

### Unit Tests

* Client success (200, valid JSON, empty findings)
* Authentication (401)
* Rate limit (429 + Retry-After)
* Timeout
* Transport failure
* Other HTTP errors (500, etc.)
* Malformed API response
* Empty choices/content
* Invalid structured JSON
* Invalid schema
* Mapper correctness
* Adapter protocol compliance
* Execution trace
* Runtime metadata
* API key redaction

### Architecture Boundary Tests

* OpenRouter does not import intelligence
* OpenRouter does not import workspace
* Provider models do not import domain
* Only mapper crosses provider/domain boundary
* Domain does not import OpenRouter
* Application does not import OpenRouter

### Integration Tests

* Pipeline → Registry → OpenRouter adapter
* Mocked HTTP transport (no real API calls)

---

## Registration

### Factory

```python
from app.core.inference.infrastructure.composition import create_openrouter_adapter

adapter = create_openrouter_adapter()
```

Validates configuration and constructs a ready-to-use adapter.

### Registry

```python
from app.core.inference.infrastructure.composition import register_openrouter_adapter

register_openrouter_adapter(registry, product_key="my-product")
```

Registers the adapter for a specific product key.

### Runtime Integration

The OpenRouter adapter is **not auto-registered** globally. Runtime composition must explicitly wire it through:

```python
registry = InferenceRegistry()
register_openrouter_adapter(registry, "my-product")
pipeline = InferencePipeline(registry)
```

---

## Next Integration Point

### Clinical Product Adapters

Future clinical product adapters (e.g., Retina, CBC, ECG) should:

1. Remain separate from the generic OpenRouter adapter
2. Implement their own `InferenceAdapter`
3. Use OpenRouter (or another provider) as an HTTP transport
4. Contain product-specific clinical reasoning
5. Resolve real clinical context
6. Register with unique product keys

The OpenRouter adapter provides the **foundational provider layer** but does not replace product-specific adapters.

---

## Known Limitations

1. **No clinical context resolution:** `context_reference` is treated as opaque.
2. **No retries:** The adapter makes a single HTTP request per inference.
3. **No fallback models:** Uses the configured model only.
4. **No streaming:** Structured output requires a complete response.
5. **Provider-specific:** Tightly coupled to OpenRouter's OpenAI-compatible API.

---

## Maintenance

### Adding New Error Types

1. Define the exception in `errors.py`
2. Map HTTP status/transport failure in `client.py`
3. Add tests covering the new error path
4. Document the error in this file

### Changing Structured Output Schema

1. Update `OpenRouterStructuredOutput` in `models.py`
2. Update `prompts.py` to instruct the model correctly
3. Update `mapper.py` if domain mapping changes
4. Update tests to cover the new schema
5. Version the schema if it's a breaking change

### Replacing OpenRouter

1. Implement a new provider under `providers/<new_provider>/`
2. Follow the same boundary rules
3. Implement `InferenceAdapter`
4. Create a new composition helper
5. Register with a product key
6. OpenRouter remains available for other products

---

## References

* Inference Runtime Foundation: `app/core/inference/`
* Domain Models: `app/core/inference/domain/models.py`
* Adapter Protocol: `app/core/inference/application/adapter.py`
* Pipeline: `app/core/inference/application/pipeline.py`
* Registry: `app/core/inference/application/registry.py`
* Tests: `backend/tests/test_openrouter_inference_adapter.py`
* Boundary Tests: `backend/tests/test_openrouter_boundaries.py`
