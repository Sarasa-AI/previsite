"""Composition boundary: assemble OrchestratorInputs for a session.

`WorkspaceOrchestrator.compute` accepts an `OrchestratorInputs` bundle carrying the
facts that are deliberately *not* first-class on `ClinicalContext`. Until this
module existed nothing supplied that bundle, so every request computed a plan from
`OrchestratorInputs()` defaults. The practical consequence was that RED_FLAGS,
CONFLICTS and DOCUMENTS were permanently `hidden / NO_DATA` in the Doctor
Workspace even when the very same session had red flags in its intake summary,
validated SOAP discrepancies on disk, and uploaded documents in the files table.

Directional rules preserved here:
- Workspace may *consume* Clinical Intelligence adapter output; Intelligence never
  imports Workspace.
- Clinical facts come from ClinicalContext; the database is consulted only for
  facts the aggregate intentionally excludes (document count, persisted SOAP
  conflicts, persisted findings).
"""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File as FileModel
from app.models import Summary
from app.modules.intelligence.application.adapters.workspace_signals import (
    to_finding_signal_bundle,
)
from app.modules.intelligence.infrastructure.finding_repository import (
    SqlAlchemyFindingRepository,
)
from app.modules.workspace.application.compose_intelligence_signals import (
    orchestrator_inputs_from_finding_bundle,
)
from app.modules.workspace.application.context_signals import (
    allergies_status_unknown,
    patient_questions_from_context,
    red_flags_from_context,
)
from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    ValidatedConflict,
)
from app.schemas.clinical_context import ClinicalContext


async def _count_documents(db: AsyncSession, session_id: int) -> int:
    """Authoritative uploaded-document count for the session.

    Previously the orchestrator fell back to ``len(context.file_analyses)``, which
    counts *derived evidence bundles* — so a session with medications but no files
    showed a Documents card, and a session with an un-OCR'd upload showed none.
    """
    result = await db.execute(
        select(func.count(FileModel.id)).where(FileModel.session_id == session_id)
    )
    return int(result.scalar_one() or 0)


def _medication_tokens(context: ClinicalContext) -> set[str]:
    tokens: set[str] = set()
    overview = context.overview
    if overview:
        for med in overview.current_medications:
            name = med.name.strip().lower()
            if name:
                tokens.add(name)
    for med in context.medication_evidence:
        name = med.name.strip().lower()
        if name:
            tokens.add(name)
    return tokens


async def _load_validated_conflicts(
    db: AsyncSession,
    session_id: int,
    context: ClinicalContext,
) -> tuple[ValidatedConflict, ...]:
    """Read persisted, PMH-validated SOAP discrepancies for this session.

    The SOAP conflict stage already applies conservative validation (high
    confidence + a quote that actually appears in the consultation), so anything
    persisted here is safe to treat as a validated conflict.
    """
    result = await db.execute(
        select(Summary.soap_conflicts_json).where(Summary.session_id == session_id)
    )
    raw = result.scalar_one_or_none()
    if not raw:
        return ()

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Unparsable soap_conflicts_json session_id={}; treating as no conflicts",
            session_id,
        )
        return ()
    if not isinstance(parsed, list):
        return ()

    med_tokens = _medication_tokens(context)

    conflicts: list[ValidatedConflict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept") or "").strip()
        if not concept:
            continue
        confidence = "high" if item.get("confidence") == "high" else "low"
        lowered = concept.lower()
        involves_medication = any(
            token and (token in lowered or lowered in token) for token in med_tokens
        )
        conflicts.append(
            ValidatedConflict(
                concept=concept,
                confidence=confidence,  # type: ignore[arg-type]
                involves_medication=involves_medication,
            )
        )
    return tuple(conflicts)


async def load_orchestrator_inputs(
    db: AsyncSession,
    session_id: int,
    context: ClinicalContext,
) -> OrchestratorInputs:
    """Build the full OrchestratorInputs bundle for one session.

    Context-derived signals (red flags, patient questions, allergy-status) are
    always computed — they need no I/O and must never silently vanish.

    The three database-backed sources are *additive*: a plan is still correct and
    renderable without them, so each is guarded independently and a failure is
    logged loudly rather than turned into a 500 that blanks the whole workspace.
    """
    red_flags = red_flags_from_context(context)
    patient_questions = patient_questions_from_context(context)
    allergies_unknown = allergies_status_unknown(context)

    document_count = 0
    try:
        document_count = await _count_documents(db, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Document count unavailable session_id={} error={}", session_id, exc
        )

    validated_conflicts: tuple[ValidatedConflict, ...] = ()
    try:
        validated_conflicts = await _load_validated_conflicts(db, session_id, context)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Validated conflicts unavailable session_id={} error={}", session_id, exc
        )

    base = OrchestratorInputs(
        red_flags=red_flags,
        patient_questions=patient_questions,
        validated_conflicts=validated_conflicts,
        allergies_status_unknown=allergies_unknown,
        document_count=document_count,
    )

    # Clinical Intelligence findings (when the pipeline has produced any) fold into
    # red_flags / validated_conflicts inside extract_signals, keeping all signal
    # merge logic in one place.
    try:
        findings = await SqlAlchemyFindingRepository(db).list_findings_for_session(
            session_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Clinical Intelligence findings unavailable session_id={} error={}",
            session_id,
            exc,
        )
        return base

    if not findings:
        return base

    bundle = to_finding_signal_bundle(session_id, list(findings))
    return orchestrator_inputs_from_finding_bundle(bundle, base=base)


def context_only_orchestrator_inputs(context: ClinicalContext) -> OrchestratorInputs:
    """Inputs derivable from ClinicalContext alone (no I/O).

    Used as the deterministic fallback when no database session is available.
    """
    return OrchestratorInputs(
        red_flags=red_flags_from_context(context),
        patient_questions=patient_questions_from_context(context),
        allergies_status_unknown=allergies_status_unknown(context),
    )


__all__ = ["context_only_orchestrator_inputs", "load_orchestrator_inputs"]
