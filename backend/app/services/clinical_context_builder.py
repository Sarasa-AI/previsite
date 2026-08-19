from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Intake, Message, Session as DBSession, Summary
from app.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from app.models import File as FileModel
from app.modules.timeline.application.timeline_builder import TimelineBuilder
from app.schemas.clinical_context import (
    ClinicalChatMessage,
    ClinicalContext,
    DocumentEvidence,
    DocumentValueEvidence,
    EvidenceProvenance,
    FileAnalysisEvidence,
    LabEvidence,
    LabResultEvidence,
    MedicationEvidence,
    MedicationEvidenceItem,
)
from app.schemas.intake import MedicalOverview
from app.schemas.medical import MedicalSummary
from app.schemas.pmh import PMHAnswer, PMHAssertion
from app.services.medical_overview_service import (
    format_conditions_for_summary,
    format_medication_for_summary,
    load_medical_overview_from_intake,
)
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage, pipeline_stage_sync
from app.services.pmh_service import (
    build_pmh_assertion_registry,
    format_pmh_for_prompt,
    get_patient_overview,
    get_patient_pmh,
)

logger = logging.getLogger(__name__)


def _summary_text_field(value: str | None) -> list[str]:
    if not value or value.strip().lower() in {"نامشخص", "unknown", "n/a", ""}:
        return []
    return [value.strip()]


def _overview_allergies_list(allergies: str) -> list[str]:
    if not allergies or not allergies.strip():
        return []
    return [part.strip() for part in allergies.split("،") if part.strip()]


def _build_additional_notes(clinical: dict) -> str | None:
    parts: list[str] = []
    hpi = (clinical.get("hpi_summary") or "").strip()
    if hpi:
        parts.append(hpi)

    red_flags = [str(x).strip() for x in (clinical.get("red_flags") or []) if str(x).strip()]
    if red_flags:
        parts.append("Red flags: " + "; ".join(red_flags))

    positives = [
        str(x).strip() for x in (clinical.get("pertinent_positives") or []) if str(x).strip()
    ]
    if positives:
        parts.append("Pertinent positives: " + "; ".join(positives))

    negatives = [
        str(x).strip() for x in (clinical.get("pertinent_negatives") or []) if str(x).strip()
    ]
    if negatives:
        parts.append("Pertinent negatives: " + "; ".join(negatives))

    patient_questions = [
        str(x).strip() for x in (clinical.get("patient_questions") or []) if str(x).strip()
    ]
    if patient_questions:
        parts.append("Patient questions: " + "; ".join(patient_questions))

    return "\n".join(parts) if parts else None


def _build_medical_summary_from_intake(intake: Intake) -> MedicalSummary | None:
    demographics = json.loads(intake.demographics_json) if intake.demographics_json else {}
    clinical = json.loads(intake.clinical_summary_json) if intake.clinical_summary_json else {}
    overview = load_medical_overview_from_intake(intake)

    if not clinical:
        return None

    past_medical_history = (
        _summary_text_field(format_conditions_for_summary(overview.chronic_conditions))
        if overview
        else []
    )

    return MedicalSummary(
        chief_complaint=clinical.get("chief_complaint") or demographics.get("chief_complaint"),
        past_medical_history=past_medical_history,
        current_medications=[
            formatted
            for med in overview.current_medications
            if (formatted := format_medication_for_summary(med))
        ]
        if overview
        else [],
        allergies=_overview_allergies_list(overview.allergies) if overview else [],
        additional_notes=_build_additional_notes(clinical),
        is_hpi_complete=True,
    )


def _build_medical_summary_from_chat(summary: Summary) -> MedicalSummary:
    return MedicalSummary(
        chief_complaint=summary.chief_complaint,
        past_medical_history=_summary_text_field(summary.past_medical_history),
        current_medications=_summary_text_field(summary.medications),
        allergies=_summary_text_field(summary.allergies),
        additional_notes=summary.history_present_illness,
        is_hpi_complete=getattr(summary, "is_hpi_complete", False) or False,
    )


def format_overview_for_soap_prompt(overview: MedicalOverview) -> str:
    lines: list[str] = []

    if overview.chronic_conditions:
        lines.append("[Chronic Conditions]")
        for condition in overview.chronic_conditions:
            label = condition.name.strip()
            duration = condition.duration.strip()
            if duration:
                lines.append(f"- {label} ({duration})")
            else:
                lines.append(f"- {label}")
        lines.append("")

    if overview.surgical_history and overview.surgical_history.strip():
        lines.append("[Surgical History]")
        lines.append(overview.surgical_history.strip())
        lines.append("")

    if overview.family_history and overview.family_history.strip():
        lines.append("[Family History]")
        lines.append(overview.family_history.strip())
        lines.append("")

    if overview.allergies and overview.allergies.strip():
        lines.append("[Allergies]")
        lines.append(overview.allergies.strip())
        lines.append("")

    if overview.current_medications:
        med_lines = [
            formatted
            for med in overview.current_medications
            if (formatted := format_medication_for_summary(med))
        ]
        if med_lines:
            lines.append("[Current Medications]")
            for med_line in med_lines:
                lines.append(f"- {med_line}")
            lines.append("")

    if overview.patient_questions and overview.patient_questions.strip():
        lines.append("[Patient Questions]")
        lines.append(overview.patient_questions.strip())
        lines.append("")

    return "\n".join(lines).strip()


def build_overview_assertion_registry(overview: MedicalOverview) -> list[PMHAssertion]:
    assertions: list[PMHAssertion] = []
    for condition in overview.chronic_conditions:
        name = condition.name.strip()
        if not name:
            continue
        assertions.append(
            PMHAssertion(
                assertion_id=condition.id,
                concept=name,
                subcategory=None,
                category_id="overview_chronic",
                polarity="present",
                detail=condition.duration.strip() or None,
            )
        )
    return assertions


def _derive_lab_and_file_evidence(
    overview: MedicalOverview | None,
) -> tuple[tuple[LabEvidence, ...], tuple[FileAnalysisEvidence, ...]]:
    if not overview:
        return (), ()

    labs: list[LabEvidence] = []
    analyses: list[FileAnalysisEvidence] = []

    for lab in overview.lab_results:
        extracted = (lab.extracted_data or "").strip()
        labs.append(
            LabEvidence(
                lab_id=lab.id,
                name=lab.name,
                extracted_data=extracted or None,
            )
        )
        if extracted:
            analyses.append(
                FileAnalysisEvidence(
                    lab_results=(
                        LabResultEvidence(
                            test_name=lab.name,
                            value=extracted,
                            unit=None,
                        ),
                    )
                )
            )

    return tuple(labs), tuple(analyses)


def _derive_medication_evidence(
    overview: MedicalOverview | None,
) -> tuple[tuple[MedicationEvidence, ...], tuple[FileAnalysisEvidence, ...]]:
    if not overview or not overview.current_medications:
        return (), ()

    meds: list[MedicationEvidence] = []
    items: list[MedicationEvidenceItem] = []

    for med in overview.current_medications:
        name = med.name.strip()
        if not name and not med.amount.strip() and not med.frequency.strip():
            continue
        display_name = name or "نامشخص - تصویر پیوست شد"
        meds.append(
            MedicationEvidence(
                medication_id=med.id,
                name=display_name,
                amount=med.amount,
                frequency=med.frequency,
            )
        )
        items.append(
            MedicationEvidenceItem(
                name=display_name,
                dose=med.amount.strip() or None,
                frequency=med.frequency.strip() or None,
            )
        )

    if not items:
        return tuple(meds), ()

    return tuple(meds), (FileAnalysisEvidence(medications=tuple(items)),)


def _compose_pmh_context(
    overview: MedicalOverview | None,
    pmh_answers: list[PMHAnswer],
) -> str | None:
    parts: list[str] = []
    if overview:
        overview_text = format_overview_for_soap_prompt(overview)
        if overview_text:
            parts.append(overview_text)
    if pmh_answers:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy_text = format_pmh_for_prompt(pmh_answers)
        if legacy_text:
            parts.append(legacy_text)
    return "\n\n".join(parts).strip() or None


def _bbox_from_payload(raw: object) -> tuple[int, int, int, int] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        left, top, width, height = (int(value) for value in raw)
    except (TypeError, ValueError):
        return None
    return (left, top, width, height)


def _document_values(
    payload: dict,
    *,
    document_id: int,
    document_name: str,
) -> tuple[DocumentValueEvidence, ...]:
    raw_values = payload.get("values")
    if not isinstance(raw_values, list):
        return ()

    values: list[DocumentValueEvidence] = []
    for raw in raw_values:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        value = str(raw.get("value") or "").strip()
        if not name or not value:
            continue
        provenance_raw = raw.get("provenance")
        provenance_raw = provenance_raw if isinstance(provenance_raw, dict) else {}
        page_raw = provenance_raw.get("page")
        try:
            page = int(page_raw) if page_raw is not None else None
        except (TypeError, ValueError):
            page = None
        confidence_raw = provenance_raw.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else None
        except (TypeError, ValueError):
            confidence = None

        unit = raw.get("unit")
        review_reason = raw.get("review_reason")
        values.append(
            DocumentValueEvidence(
                name=name,
                value=value,
                unit=str(unit).strip() if unit else None,
                abnormal=bool(raw.get("abnormal")),
                needs_review=bool(raw.get("needs_review")),
                review_reason=str(review_reason) if review_reason else None,
                provenance=EvidenceProvenance(
                    document_id=document_id,
                    document_name=document_name,
                    page=page,
                    bbox=_bbox_from_payload(provenance_raw.get("bbox")),
                    source_text=str(provenance_raw.get("source_text") or ""),
                    confidence=confidence,
                    method=str(provenance_raw.get("method") or ""),
                ),
            )
        )
    return tuple(values)


async def _load_document_evidence(
    db: AsyncSession, session_id: int
) -> tuple[DocumentEvidence, ...]:
    """Project persisted DocumentArtifacts into source evidence for the aggregate.

    Reads the extraction artifact per file and joins the paired OCR artifact's
    status so a failed/unavailable transcription stays visible rather than looking
    like "this document simply had no values".
    """
    file_result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id).order_by(FileModel.id)
    )
    files_by_id = {row.id: row for row in file_result.scalars().all()}
    if not files_by_id:
        return ()

    artifact_result = await db.execute(
        select(DocumentArtifact)
        .where(DocumentArtifact.session_id == session_id)
        .order_by(DocumentArtifact.file_id.asc(), DocumentArtifact.id.asc())
    )
    artifacts = list(artifact_result.scalars().all())
    if not artifacts:
        return ()

    # Last artifact per (file, kind) wins — reprocessing appends, never mutates.
    latest: dict[tuple[int, str], DocumentArtifact] = {}
    for artifact in artifacts:
        latest[(artifact.file_id, artifact.kind)] = artifact

    evidence: list[DocumentEvidence] = []
    for file_id in sorted({key[0] for key in latest}):
        db_file = files_by_id.get(file_id)
        if db_file is None:
            continue
        ocr = latest.get((file_id, ArtifactKind.OCR))
        extraction = latest.get((file_id, ArtifactKind.EXTRACTION))
        if ocr is None and extraction is None:
            continue

        filename = db_file.filename or ""
        values: tuple[DocumentValueEvidence, ...] = ()
        payload: dict = {}
        if extraction is not None and extraction.payload_json:
            try:
                loaded = json.loads(extraction.payload_json)
            except json.JSONDecodeError:
                logger.warning(
                    "Unparsable extraction payload artifact_id=%s file_id=%s",
                    extraction.id,
                    file_id,
                )
                loaded = None
            if isinstance(loaded, dict):
                payload = loaded
                values = _document_values(
                    payload, document_id=file_id, document_name=filename
                )

        needs_review = bool(payload.get("needs_review")) or any(
            value.needs_review for value in values
        )
        statuses = {
            artifact.status
            for artifact in (ocr, extraction)
            if artifact is not None
        }
        if ArtifactStatus.NEEDS_REVIEW in statuses or ArtifactStatus.FAILED in statuses:
            needs_review = True

        error_detail = next(
            (
                artifact.error_detail
                for artifact in (extraction, ocr)
                if artifact is not None and artifact.error_detail
            ),
            None,
        )

        evidence.append(
            DocumentEvidence(
                document_id=file_id,
                filename=filename,
                ocr_status=ocr.status if ocr is not None else "",
                extraction_status=extraction.status if extraction is not None else "",
                engine=(ocr.engine if ocr is not None else "") or "",
                page_count=(ocr.page_count if ocr is not None else None),
                needs_review=needs_review,
                error_detail=error_detail,
                values=values,
            )
        )

    return tuple(evidence)


def _document_derived_evidence(
    documents: tuple[DocumentEvidence, ...],
) -> tuple[tuple[LabEvidence, ...], tuple[FileAnalysisEvidence, ...]]:
    """Derive lab + file-analysis evidence from document extractions.

    Values still flagged ``needs_review`` are deliberately excluded from the
    trusted lab surfaces: an unconfirmed transcription must not read as a
    confirmed result. They remain visible on ``document_evidence`` so the
    physician can review them with their provenance.
    """
    labs: list[LabEvidence] = []
    analyses: list[FileAnalysisEvidence] = []

    for document in documents:
        trusted = [value for value in document.values if not value.needs_review]
        if not trusted:
            continue

        lab_rows: list[LabResultEvidence] = []
        for value in trusted:
            rendered = value.value if not value.unit else f"{value.value} {value.unit}"
            labs.append(
                LabEvidence(
                    lab_id=f"doc-{document.document_id}-{value.name.lower().replace(' ', '-')}",
                    name=value.name,
                    extracted_data=rendered,
                )
            )
            lab_rows.append(
                LabResultEvidence(
                    test_name=value.name,
                    value=value.value,
                    unit=value.unit,
                )
            )

        analyses.append(FileAnalysisEvidence(lab_results=tuple(lab_rows)))

    return tuple(labs), tuple(analyses)


class ClinicalContextBuilder:
    """Assemble a single immutable ClinicalContext for SOAP and future Clinical AI modules."""

    async def build(self, db: AsyncSession, session_id: int) -> ClinicalContext:
        # Outer clinical_context.build timing is owned by soap_task callers.
        session_result = await db.execute(
            select(DBSession).where(DBSession.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        patient_id = session.patient_id

        msg_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        db_messages = msg_result.scalars().all()
        chat_history = tuple(
            ClinicalChatMessage(
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in db_messages
        )

        sum_result = await db.execute(
            select(Summary).where(Summary.session_id == session_id)
        )
        summary_row = sum_result.scalar_one_or_none()

        intake_result = await db.execute(
            select(Intake).where(Intake.session_id == session_id)
        )
        intake = intake_result.scalar_one_or_none()

        async with pipeline_stage(
            PipelineStage.PMH_LOAD,
            module=PipelineModule.PMH,
            session_id=session_id,
            patient_id=patient_id,
            emit_event=True,
        ):
            overview = load_medical_overview_from_intake(intake) if intake else None
            if overview is None:
                overview = await get_patient_overview(db, patient_id)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                legacy_answers = await get_patient_pmh(db, patient_id)
            pmh_answers = tuple(legacy_answers or [])

        med_sum: MedicalSummary | None = None
        if intake and intake.clinical_summary_json:
            med_sum = _build_medical_summary_from_intake(intake)
        elif summary_row:
            med_sum = _build_medical_summary_from_chat(summary_row)

        if not med_sum:
            raise ValueError("No clinical summary available for ClinicalContext")

        lab_evidence, lab_analyses = _derive_lab_and_file_evidence(overview)
        medication_evidence, med_analyses = _derive_medication_evidence(overview)

        # Document artifacts are the canonical, provenance-carrying source for
        # anything transcribed from an uploaded file. Intake-bound lab slots stay
        # in play for values the patient typed or that the synchronous upload OCR
        # echoed back.
        document_evidence = await _load_document_evidence(db, session_id)
        doc_labs, doc_analyses = _document_derived_evidence(document_evidence)

        seen_lab_names = {lab.name.strip().lower() for lab in lab_evidence if lab.name}
        merged_labs = list(lab_evidence)
        for lab in doc_labs:
            if lab.name.strip().lower() in seen_lab_names:
                continue
            seen_lab_names.add(lab.name.strip().lower())
            merged_labs.append(lab)
        lab_evidence = tuple(merged_labs)

        file_analyses = lab_analyses + med_analyses + doc_analyses

        overview_assertions = (
            build_overview_assertion_registry(overview) if overview else []
        )
        legacy_assertions = (
            build_pmh_assertion_registry(list(pmh_answers)) if pmh_answers else []
        )
        # Prefer legacy questionnaire assertions when present; always include overview conditions.
        seen_ids = {a.assertion_id for a in legacy_assertions}
        merged_assertions = list(legacy_assertions)
        for assertion in overview_assertions:
            if assertion.assertion_id not in seen_ids:
                merged_assertions.append(assertion)
                seen_ids.add(assertion.assertion_id)

        pmh_context = _compose_pmh_context(overview, list(pmh_answers))

        context = ClinicalContext(
            session_id=session_id,
            patient_id=patient_id,
            summary=med_sum,
            chat_history=chat_history,
            overview=overview,
            pmh_context=pmh_context,
            pmh_answers=pmh_answers,
            pmh_assertions=tuple(merged_assertions),
            file_analyses=file_analyses,
            lab_evidence=lab_evidence,
            medication_evidence=medication_evidence,
            document_evidence=document_evidence,
        )

        anchor_at = datetime.now(timezone.utc)
        with pipeline_stage_sync(
            PipelineStage.TIMELINE_BUILD,
            module=PipelineModule.TIMELINE,
            session_id=session_id,
            patient_id=patient_id,
            emit_event=True,
        ) as stage:
            timeline = TimelineBuilder().build(context, anchor_at=anchor_at)
            stage.attrs["evidence_count"] = len(timeline.events)
            context = context.model_copy(update={"timeline": timeline})

        return context


clinical_context_builder = ClinicalContextBuilder()
