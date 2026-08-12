"""Provider-to-domain mapper — only boundary crossing provider → InferenceFinding."""

from __future__ import annotations

from app.core.inference.domain.models import InferenceFinding
from app.core.inference.infrastructure.providers.openrouter.errors import (
    OpenRouterStructuredOutputError,
)
from app.core.inference.infrastructure.providers.openrouter.models import (
    OpenRouterProviderFinding,
    OpenRouterStructuredOutput,
)


def map_structured_output_to_findings(
    structured_output: OpenRouterStructuredOutput,
) -> tuple[InferenceFinding, ...]:
    """Map provider structured output to domain InferenceFinding objects.

    Parameters
    ----------
    structured_output : OpenRouterStructuredOutput
        Validated provider model output.

    Returns
    -------
    tuple[InferenceFinding, ...]
        Domain inference findings.

    Raises
    ------
    OpenRouterStructuredOutputError
        If any provider finding cannot be mapped to a valid domain finding.

    Notes
    -----
    This is the only place where provider models cross into the inference domain.
    All mapping failures are explicit; no silent dropping of findings.
    """
    findings: list[InferenceFinding] = []

    for idx, provider_finding in enumerate(structured_output.findings):
        try:
            domain_finding = _map_single_finding(provider_finding)
            findings.append(domain_finding)
        except Exception as exc:
            raise OpenRouterStructuredOutputError(
                f"Failed to map provider finding at index {idx} "
                f"(finding_key={provider_finding.finding_key!r}): {exc}"
            ) from exc

    return tuple(findings)


def _map_single_finding(
    provider_finding: OpenRouterProviderFinding,
) -> InferenceFinding:
    """Map a single provider finding to a domain InferenceFinding.

    Raises
    ------
    ValueError
        If domain validation fails (e.g., invalid confidence, empty required fields).
    """
    return InferenceFinding(
        artifact_type=provider_finding.artifact_type,
        finding_key=provider_finding.finding_key,
        title=provider_finding.title,
        summary=provider_finding.summary,
        confidence=provider_finding.confidence,
        attributes=dict(provider_finding.attributes),
    )
