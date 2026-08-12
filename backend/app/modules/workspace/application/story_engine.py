"""Story Engine — evidence-bound template narrative (no AI / no diagnosis)."""

from __future__ import annotations

from app.modules.workspace.application.inputs import ReviewAcknowledgements
from app.modules.workspace.application.priority_engine import ObjectPriority
from app.modules.workspace.application.role_profiles import RoleClamp
from app.modules.workspace.application.signals import WorkspaceSignals
from app.modules.workspace.domain.enums import VisibilityReason
from app.modules.workspace.domain.models import ClinicalStory, STORY_MAX_CHARS, STORY_MAX_WORDS


def _truncate_words(text: str, max_words: int = STORY_MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _limit_sentences(parts: list[str], max_sentences: int = 4) -> str:
    """Join at most max_sentences sentences into one story string."""
    limited = parts[:max_sentences]
    return _truncate_words(" ".join(limited))


def generate_story(
    signals: WorkspaceSignals,
    role: RoleClamp,
    review: ReviewAcknowledgements,
    story_assessment: ObjectPriority,
) -> ClinicalStory | None:
    """
    Build a short evidence-bound orientation narrative.

    No diagnosis, recommendations, or invented facts — template only.
    """
    if not role.story_enabled:
        story_assessment.hidden = True
        story_assessment.present = False
        story_assessment.visibility_reason = VisibilityReason.SPECIALTY_FILTER
        return None

    if signals.offline:
        story_assessment.hidden = True
        story_assessment.present = False
        story_assessment.visibility_reason = VisibilityReason.DEPENDENCY_UNAVAILABLE
        return None

    has_support = signals.timeline_event_count >= 3 or (
        signals.has_chief_complaint
        and (
            signals.has_labs
            or signals.medication_count > 0
            or signals.has_pmh_content
        )
    )
    if not has_support:
        story_assessment.hidden = True
        story_assessment.present = False
        story_assessment.visibility_reason = VisibilityReason.NO_DATA
        return None

    parts: list[str] = []
    refs: list[str] = []

    if signals.has_chief_complaint and signals.chief_complaint:
        parts.append(f"Patient presents for {signals.chief_complaint.strip()}.")
        refs.append("summary.chief_complaint")

    if signals.timeline_event_count > 0:
        parts.append(
            f"Timeline includes {signals.timeline_event_count} dated clinical events."
        )
        refs.append("context.timeline")

    if signals.medication_count > 0:
        parts.append(f"Current medication list has {signals.medication_count} entries.")
        refs.append("overview.current_medications")
    elif signals.has_labs:
        if signals.has_critical_labs:
            parts.append("Laboratory evidence includes critical markers.")
        else:
            parts.append("Laboratory evidence is available for review.")
        refs.append("lab_evidence")

    if signals.has_allergy_documented and len(parts) < 4:
        parts.append("Allergy information is documented.")
        refs.append("overview.allergies")
    elif signals.validated_conflicts and len(parts) < 4:
        parts.append(
            f"{len(signals.validated_conflicts)} validated conflict(s) remain unresolved."
        )
        refs.append("validated_conflicts")

    if not parts or not refs:
        story_assessment.hidden = True
        story_assessment.present = False
        story_assessment.visibility_reason = VisibilityReason.GENERATION_FAILED
        return None

    text = _limit_sentences(parts, max_sentences=4)
    if len(text) > STORY_MAX_CHARS:
        text = text[: STORY_MAX_CHARS - 1].rsplit(" ", 1)[0] + "."

    coverage = min(1.0, len(refs) / 4.0)
    confidence = round(max(0.5, coverage), 2)
    if confidence < 0.5:
        story_assessment.hidden = True
        story_assessment.present = False
        story_assessment.visibility_reason = VisibilityReason.GENERATION_FAILED
        return None

    story_assessment.hidden = False
    story_assessment.present = True
    story_assessment.visibility_reason = None

    return ClinicalStory(
        text=text,
        confidence=confidence,
        evidence_refs=tuple(dict.fromkeys(refs)),
        stale=review.story_frozen and not review.story_refresh_requested,
    )
