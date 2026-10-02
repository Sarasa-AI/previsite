from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from app.schemas.pmh import ClinicalDiscrepancy, PMHAssertion


_CONFLICTS_START = "<<<CLINICAL_CONFLICTS>>>"
_CONFLICTS_END = "<<<END_CLINICAL_CONFLICTS>>>"


@dataclass(frozen=True)
class ConflictParseResult:
    soap_body: str
    raw_items: list[dict]


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fuzzy_contains(haystack: str, needle: str, *, min_ratio: float = 0.75) -> bool:
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True
    a = _normalize(haystack)
    b = _normalize(needle)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= min_ratio


def split_conflict_footer(llm_output: str) -> ConflictParseResult:
    """
    Split an LLM output into:
    - soap_body: user-facing Markdown SOAP note (footer removed)
    - raw_items: parsed list of dicts from the machine footer

    If no footer exists or parsing fails, returns the original body and [].
    """
    if not llm_output:
        return ConflictParseResult(soap_body="", raw_items=[])

    start = llm_output.rfind(_CONFLICTS_START)
    end = llm_output.rfind(_CONFLICTS_END)
    if start == -1 or end == -1 or end < start:
        return ConflictParseResult(soap_body=llm_output.strip(), raw_items=[])

    body = llm_output[:start].rstrip()
    payload = llm_output[start + len(_CONFLICTS_START) : end].strip()
    try:
        parsed = json.loads(payload) if payload else []
        if not isinstance(parsed, list):
            return ConflictParseResult(soap_body=body, raw_items=[])
        items: list[dict] = [x for x in parsed if isinstance(x, dict)]
        return ConflictParseResult(soap_body=body, raw_items=items)
    except Exception:
        return ConflictParseResult(soap_body=body, raw_items=[])


def validate_conflicts(
    *,
    raw_items: list[dict],
    pmh_registry: list[PMHAssertion],
    chat_history: list[dict] | None,
) -> list[ClinicalDiscrepancy]:
    """
    Validate LLM-proposed conflicts against a deterministic PMH registry + chat quotes.

    Conservative: only keep conflicts with confidence=high and a quote that appears in chat.
    """
    registry_by_id = {a.assertion_id: a for a in pmh_registry}
    chat_text = "\n".join((m.get("content") or "") for m in (chat_history or [])).strip()

    validated: list[ClinicalDiscrepancy] = []
    seen_concepts: set[str] = set()

    for item in raw_items:
        pmh_assertion_id = item.get("pmh_assertion_id")
        chat_polarity = item.get("chat_polarity")
        chat_quote = item.get("chat_quote") or ""
        concept = item.get("concept") or ""
        confidence = item.get("confidence")

        if confidence != "high":
            continue
        if not isinstance(pmh_assertion_id, str) or pmh_assertion_id not in registry_by_id:
            continue
        if chat_polarity not in {"affirm", "deny"}:
            continue
        if not isinstance(chat_quote, str) or not chat_quote.strip():
            continue
        if not _fuzzy_contains(chat_text, chat_quote.strip()):
            continue

        pmh = registry_by_id[pmh_assertion_id]

        # Allowed conflict matrix (only contradictions)
        if pmh.polarity == "present" and chat_polarity != "deny":
            continue
        if pmh.polarity == "category_denied" and chat_polarity != "affirm":
            continue

        final_concept = concept.strip() or pmh.concept
        if final_concept in seen_concepts:
            continue
        seen_concepts.add(final_concept)

        validated.append(
            ClinicalDiscrepancy(
                pmh_assertion_id=pmh_assertion_id,
                concept=final_concept,
                pmh_polarity=pmh.polarity,
                chat_polarity=chat_polarity,
                chat_quote=chat_quote.strip(),
                confidence="high",
            )
        )

    return validated


def format_discrepancy_alert(discrepancies: Iterable[ClinicalDiscrepancy]) -> str:
    items = list(discrepancies)
    if not items:
        return ""

    lines: list[str] = []
    lines.append("### ⚠️ Clinical Discrepancy Alert")
    lines.append("")
    lines.append(
        "The following statements from today's consultation conflict with the structured PMH questionnaire on file. Please verify with the patient."
    )
    lines.append("")

    for i, d in enumerate(items, start=1):
        lines.append(f"{i}. **{d.concept}**")
        if d.pmh_polarity == "present":
            lines.append("   - *PMH questionnaire:* Reported as present")
            lines.append(f"   - *Consultation:* \"{d.chat_quote}\" (patient denial)")
        else:
            lines.append("   - *PMH questionnaire:* Category declined / not provided")
            lines.append(f"   - *Consultation:* \"{d.chat_quote}\"")
        lines.append("   - *Action:* Confirm history with the patient; update PMH if appropriate.")
        lines.append("")

    lines.append("---")
    lines.append("*This alert is auto-generated. It does not replace clinical judgment.*")
    return "\n".join(lines).strip()


def validate_and_format_conflicts(
    *,
    llm_output: str,
    pmh_registry: list[PMHAssertion],
    chat_history: list[dict] | None,
) -> tuple[str, list[ClinicalDiscrepancy]]:
    parsed = split_conflict_footer(llm_output)
    conflicts = validate_conflicts(
        raw_items=parsed.raw_items, pmh_registry=pmh_registry, chat_history=chat_history
    )
    return parsed.soap_body, conflicts

