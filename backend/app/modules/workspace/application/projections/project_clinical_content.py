"""Deterministic ClinicalContext → ClinicalContentResponse projection.

Pure function: same ClinicalContext + identical adapters → identical response.
Clinical facts always read from ClinicalContext. Adapters supply non-clinical only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from app.modules.workspace.application.context_hash import compute_context_hash
from app.modules.workspace.application.context_signals import parse_red_flags
from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    SoapAdapter,
)
from app.modules.workspace.interface.clinical_content_dto import (
    CONTENT_VERSION,
    ChiefComplaintContentDTO,
    ClinicalContentBodyDTO,
    ClinicalContentResponse,
    DocumentItemDTO,
    DocumentsContentDTO,
    LabRowDTO,
    LabsContentDTO,
    MedicationGroupDTO,
    MedicationItemDTO,
    MedicationsContentDTO,
    MissingInfoContentDTO,
    MissingInfoItemDTO,
    PatientHeaderContentDTO,
    RedFlagItemDTO,
    RedFlagsContentDTO,
    SnapshotStripContentDTO,
    SoapContentDTO,
    TimelineContentDTO,
    TimelineEventDTO,
    TimelineGroupDTO,
)
from app.schemas.clinical_context import ClinicalContext

_SAFETY_KEYWORDS = frozenset(
    {
        "chest pain",
        "shortness of breath",
        "sob",
        "syncope",
        "stroke",
        "anaphylaxis",
        "suicidal",
        "hemorrhage",
        "bleeding",
        "seizure",
        "unconscious",
        "critical",
        "urgent",
        "stat",
        "panic",
    }
)
_ABNORMAL_LAB_RE = re.compile(
    r"\b(critical|panic|abnormal|elevated|high|low|hh|ll|\*\*\*)\b",
    re.IGNORECASE,
)
_ASSESSMENT_RE = re.compile(
    r"(?:\*\*)?(?:A\s*[-–—]\s*)?Assessment(?:\s*\([^)]*\))?(?:\*\*)?\s*\n(.*?)(?=(?:\*\*)?(?:P\s*[-–—]\s*)?Plan|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_PLAN_RE = re.compile(
    r"(?:\*\*)?(?:P\s*[-–—]\s*)?Plan(?:\s*\([^)]*\))?(?:\*\*)?\s*\n(.*)\Z",
    re.IGNORECASE | re.DOTALL,
)


def project_clinical_content(
    context: ClinicalContext,
    adapters: ClinicalContentAdapters,
) -> ClinicalContentResponse:
    """Project ClinicalContext (+ allowed adapters) into a versioned envelope."""
    content = ClinicalContentBodyDTO(
        patient_header=_project_patient_header(adapters),
        chief_complaint=_project_chief_complaint(context),
        red_flags=_project_red_flags(context),
        snapshot=_project_snapshot(context),
        timeline=_project_timeline(context),
        medications=_project_medications(context),
        labs=_project_labs(context),
        missing_info=_project_missing_info(context),
        soap=_project_soap(adapters.soap),
        documents=_project_documents(adapters),
    )
    return ClinicalContentResponse(
        session_id=adapters.session.session_id,
        context_hash=compute_context_hash(context),
        content_version=CONTENT_VERSION,
        generated_at=adapters.session.generated_at,
        content=content,
    )


def _stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _project_patient_header(
    adapters: ClinicalContentAdapters,
) -> PatientHeaderContentDTO | None:
    demo = adapters.demographics
    if demo is None:
        return None
    name = f"{demo.first_name} {demo.last_name}".strip()
    if not name and demo.age is None and not demo.sex and not demo.national_id:
        return None
    return PatientHeaderContentDTO(
        name=name,
        age=demo.age if demo.age is not None else 0,
        sex=demo.sex or "",
        mrn=demo.national_id or "",
        visit_type=adapters.session.visit_type or "",
        status=adapters.session.status or "",
    )


def _project_chief_complaint(
    context: ClinicalContext,
) -> ChiefComplaintContentDTO | None:
    title = (context.summary.chief_complaint or "").strip()
    if not title:
        return None
    duration = (context.summary.symptom_duration or "").strip()
    if not duration and context.summary.symptom_onset:
        duration = (context.summary.symptom_onset or "").strip()
    return ChiefComplaintContentDTO(
        title=title,
        duration=duration,
        priority="",
    )


def _parse_red_flags_from_notes(notes: str | None) -> tuple[str, ...]:
    # Single shared parser with the WorkspacePlan signal path — if these two ever
    # disagree the plan hides a card whose body content exists.
    return parse_red_flags(notes)


def _red_flag_severity(title: str) -> str:
    lower = title.lower()
    if any(kw in lower for kw in _SAFETY_KEYWORDS):
        return "critical"
    return "warning"


def _project_red_flags(context: ClinicalContext) -> RedFlagsContentDTO | None:
    flags = _parse_red_flags_from_notes(context.summary.additional_notes)
    if not flags:
        return None
    items: list[RedFlagItemDTO] = []
    for flag in flags:
        items.append(
            RedFlagItemDTO(
                id=_stable_id("rf", flag),
                title=flag,
                severity=_red_flag_severity(flag),  # type: ignore[arg-type]
                explanation=flag,
            )
        )
    items.sort(key=lambda item: (item.id, item.title))
    return RedFlagsContentDTO(items=items)


def _allergy_text(context: ClinicalContext) -> str:
    if context.overview and (context.overview.allergies or "").strip():
        return context.overview.allergies.strip()
    allergies = context.summary.allergies or []
    return ", ".join(a.strip() for a in allergies if a and str(a).strip())


def _problems_text(context: ClinicalContext) -> str:
    if context.overview and context.overview.chronic_conditions:
        names = [
            c.name.strip()
            for c in context.overview.chronic_conditions
            if c.name and c.name.strip()
        ]
        names.sort()
        return ", ".join(names)
    pmh = context.summary.past_medical_history or []
    names = [str(p).strip() for p in pmh if p and str(p).strip()]
    names.sort()
    return ", ".join(names)


def _medication_count(context: ClinicalContext) -> int:
    if context.medication_evidence:
        return len(context.medication_evidence)
    if context.overview and context.overview.current_medications:
        return len(context.overview.current_medications)
    return len(context.summary.current_medications or [])


def _timeline_count(context: ClinicalContext) -> int:
    if context.timeline is None:
        return 0
    return len(context.timeline.events)


def _project_snapshot(context: ClinicalContext) -> SnapshotStripContentDTO | None:
    allergies = _allergy_text(context)
    problems = _problems_text(context)
    med_count = _medication_count(context)
    tl_count = _timeline_count(context)
    has_cc = bool((context.summary.chief_complaint or "").strip())
    if not allergies and not problems and med_count == 0 and tl_count == 0 and not has_cc:
        return None
    return SnapshotStripContentDTO(
        vitals="",
        problems=problems,
        risk="",
        allergies=allergies,
        medication_count=med_count,
        timeline_count=tl_count,
    )


def _event_date_key(event) -> str:
    temporal = event.temporal
    if temporal.absolute_datetime is not None:
        return temporal.absolute_datetime.date().isoformat()
    return "Unknown"


def _event_detail(event) -> str:
    if event.evidence:
        excerpt = (event.evidence[0].excerpt or "").strip()
        if excerpt:
            return excerpt
    return (event.temporal.raw_text or "").strip()


def _project_timeline(context: ClinicalContext) -> TimelineContentDTO | None:
    if context.timeline is None or not context.timeline.events:
        return None
    grouped: dict[str, list[TimelineEventDTO]] = defaultdict(list)
    for event in context.timeline.events:
        date_key = _event_date_key(event)
        source = event.source.value if hasattr(event.source, "value") else str(event.source)
        grouped[date_key].append(
            TimelineEventDTO(
                id=event.event_id,
                title=event.label,
                detail=_event_detail(event),
                source=source,
            )
        )
    groups: list[TimelineGroupDTO] = []
    for date_key in sorted(grouped.keys()):
        events = sorted(grouped[date_key], key=lambda e: (e.id, e.title))
        groups.append(TimelineGroupDTO(date=date_key, events=events))
    return TimelineContentDTO(groups=groups)


def _project_medications(context: ClinicalContext) -> MedicationsContentDTO | None:
    items: list[MedicationItemDTO] = []

    if context.medication_evidence:
        for med in context.medication_evidence:
            items.append(
                MedicationItemDTO(
                    id=med.medication_id,
                    name=med.name,
                    dose=med.amount or "",
                    frequency=med.frequency or "",
                    status="active",
                    source="clinical_context",
                )
            )
    elif context.overview and context.overview.current_medications:
        for med in context.overview.current_medications:
            items.append(
                MedicationItemDTO(
                    id=med.id,
                    name=med.name,
                    dose=med.amount or "",
                    frequency=med.frequency or "",
                    status="active",
                    source="clinical_context",
                )
            )
    else:
        for idx, raw in enumerate(context.summary.current_medications or []):
            name = str(raw).strip()
            if not name:
                continue
            items.append(
                MedicationItemDTO(
                    id=_stable_id("med", name, str(idx)),
                    name=name,
                    dose="",
                    frequency="",
                    status="active",
                    source="clinical_context",
                )
            )

    if not items:
        return None
    items.sort(key=lambda item: (item.id, item.name))
    return MedicationsContentDTO(
        groups=[MedicationGroupDTO(label="Current", items=items)]
    )


def _lab_abnormal(text: str) -> bool:
    return bool(_ABNORMAL_LAB_RE.search(text or ""))


def _project_labs(context: ClinicalContext) -> LabsContentDTO | None:
    rows: list[LabRowDTO] = []

    if context.lab_evidence:
        for lab in context.lab_evidence:
            extracted = (lab.extracted_data or "").strip()
            rows.append(
                LabRowDTO(
                    id=lab.lab_id,
                    name=lab.name,
                    value=extracted,
                    unit="",
                    reference_range="",
                    abnormal=_lab_abnormal(extracted),
                    trend="unknown",
                    detail=extracted,
                )
            )
    elif context.overview and context.overview.lab_results:
        for lab in context.overview.lab_results:
            extracted = (lab.extracted_data or "").strip()
            rows.append(
                LabRowDTO(
                    id=lab.id,
                    name=lab.name,
                    value=extracted,
                    unit="",
                    reference_range="",
                    abnormal=_lab_abnormal(extracted),
                    trend="unknown",
                    detail=extracted,
                )
            )

    if not rows:
        return None
    rows.sort(key=lambda row: (row.id, row.name))
    return LabsContentDTO(rows=rows)


def _project_missing_info(context: ClinicalContext) -> MissingInfoContentDTO | None:
    items: list[MissingInfoItemDTO] = []

    if not (context.summary.chief_complaint or "").strip():
        items.append(
            MissingInfoItemDTO(
                id="missing-chief-complaint",
                label="Chief complaint not recorded",
                priority="p0",
            )
        )

    allergies = _allergy_text(context)
    if not allergies:
        items.append(
            MissingInfoItemDTO(
                id="missing-allergies",
                label="Allergies not documented",
                priority="p0",
            )
        )

    if _medication_count(context) == 0:
        items.append(
            MissingInfoItemDTO(
                id="missing-medications",
                label="Current medications not recorded",
                priority="p2",
            )
        )

    if not context.summary.is_hpi_complete:
        items.append(
            MissingInfoItemDTO(
                id="missing-hpi",
                label="History of present illness incomplete",
                priority="p2",
            )
        )

    if not items:
        return None
    items.sort(key=lambda item: (item.id, item.label))
    return MissingInfoContentDTO(items=items, action_label="Review missing information")


def _parse_soap_sections(soap_note: str) -> tuple[str, str]:
    assessment_match = _ASSESSMENT_RE.search(soap_note)
    plan_match = _PLAN_RE.search(soap_note)
    assessment = assessment_match.group(1).strip() if assessment_match else ""
    plan = plan_match.group(1).strip() if plan_match else ""
    return assessment, plan


def _project_soap(soap: SoapAdapter | None) -> SoapContentDTO | None:
    if soap is None:
        return None

    if soap.legacy_soap_json:
        try:
            payload = json.loads(soap.legacy_soap_json)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            assessment = str(payload.get("assessment") or "").strip()
            plan = str(payload.get("plan") or "").strip()
            if assessment or plan:
                return SoapContentDTO(assessment=assessment, plan=plan)
            note = str(payload.get("soap_note") or "").strip()
            if note:
                assessment, plan = _parse_soap_sections(note)
                if assessment or plan:
                    return SoapContentDTO(assessment=assessment, plan=plan)
                return SoapContentDTO(assessment=note, plan="")

    note = (soap.soap_note or "").strip()
    if not note:
        return None
    assessment, plan = _parse_soap_sections(note)
    if assessment or plan:
        return SoapContentDTO(assessment=assessment, plan=plan)
    return SoapContentDTO(assessment=note, plan="")


def _project_documents(
    adapters: ClinicalContentAdapters,
) -> DocumentsContentDTO | None:
    if not adapters.documents:
        return None
    items = [
        DocumentItemDTO(
            id=str(doc.file_id),
            name=doc.filename,
            confidence="unknown",
            uploaded_at=doc.uploaded_at,
            detail=doc.detail,
        )
        for doc in adapters.documents
    ]
    items.sort(key=lambda item: (item.id, item.name))
    return DocumentsContentDTO(items=items)
