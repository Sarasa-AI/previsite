"""Source extractors that map ClinicalContext slices to candidate timeline events."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    TemporalKind,
    TemporalStatus,
)
from app.modules.timeline.domain.models import TemporalEvidence, TimelineEvent
from app.modules.timeline.infrastructure.temporal_normalizer import TemporalNormalizer
from app.schemas.clinical_context import ClinicalContext

_DIAGNOSED_RE = re.compile(
    r"(?P<label>.+?)\s+(?:diagnosed|diagnosis)\s+(?:in\s+)?(?P<when>.+)",
    re.IGNORECASE,
)
_MED_START_RE = re.compile(
    r"(?P<label>.+?)\s+(?:started|began|started\s+on)\s+(?P<when>.+)",
    re.IGNORECASE,
)
_FOR_DURATION_RE = re.compile(
    r"(?P<label>.+?)\s+for\s+(?P<when>.+)",
    re.IGNORECASE,
)
_UPLOAD_YESTERDAY_RE = re.compile(
    r"(uploaded|upload|recorded)\s+(?P<when>yesterday|today|[\w\s]+ago)",
    re.IGNORECASE,
)
_TEMPORAL_HINT_RE = re.compile(
    r"(\d+\s+(?:days?|weeks?|months?|years?)\s+ago|"
    r"for\s+\d+\s+(?:days?|weeks?|months?|years?)|"
    r"last\s+(?:week|month|year)|"
    r"since\s+\w+|"
    r"yesterday|today|"
    r"diagnosed\s+in\s+\d{4}|"
    r"\d+\s+(?:روز|هفته|ماه|سال)\s*پیش|"
    r"برای\s+\d+|"
    r"از\s*کودکی)",
    re.IGNORECASE,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _status_for_temporal(
    kind: TemporalKind,
    *,
    default: TemporalStatus,
    recurring: bool = False,
) -> TemporalStatus:
    if recurring:
        return TemporalStatus.RECURRING
    if kind == TemporalKind.RELATIVE_DURATION:
        return TemporalStatus.ONGOING
    if kind == TemporalKind.ABSOLUTE:
        return TemporalStatus.HISTORICAL
    if kind == TemporalKind.RELATIVE_SINCE:
        return TemporalStatus.ONGOING
    if kind in {TemporalKind.TODAY, TemporalKind.YESTERDAY, TemporalKind.RELATIVE_PAST}:
        return default
    return default


def _evidence(
    source: EventSource,
    excerpt: str,
    *,
    source_ref: str | None = None,
    confidence: float = 1.0,
) -> TemporalEvidence:
    return TemporalEvidence(
        source=source,
        source_ref=source_ref,
        excerpt=excerpt[:500],
        confidence=confidence,
    )


class TimelineExtractors:
    """Extract chronology candidates from ClinicalContext without diagnosis inference."""

    def __init__(self, normalizer: TemporalNormalizer | None = None) -> None:
        self._normalizer = normalizer or TemporalNormalizer()

    def extract_all(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        events.extend(self.extract_hpi(context, anchor_at=anchor_at))
        events.extend(self.extract_pmh(context, anchor_at=anchor_at))
        events.extend(self.extract_surgical(context, anchor_at=anchor_at))
        events.extend(self.extract_medications(context, anchor_at=anchor_at))
        events.extend(self.extract_labs(context, anchor_at=anchor_at))
        events.extend(self.extract_chat(context, anchor_at=anchor_at))
        events.extend(self.extract_documents(context, anchor_at=anchor_at))
        return events

    def extract_hpi(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        summary = context.summary

        chief = (summary.chief_complaint or "").strip()
        duration = (summary.symptom_duration or "").strip()
        onset = (summary.symptom_onset or "").strip()
        notes = (summary.additional_notes or "").strip()

        # Prefer structured duration / onset fields
        if chief and duration:
            temporal = self._normalizer.normalize(duration, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("hpi"),
                    event_type=EventType.SYMPTOM_ONGOING,
                    clinical_category=ClinicalCategory.SYMPTOM,
                    label=chief,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=EventSource.HPI,
                    evidence=(
                        _evidence(
                            EventSource.HPI,
                            f"{chief} for {duration}",
                            source_ref="summary.symptom_duration",
                        ),
                    ),
                    confidence=0.9,
                )
            )
        elif chief:
            # Try to parse duration from chief complaint itself ("Headache for three days")
            matched = _FOR_DURATION_RE.match(chief)
            if matched:
                label = matched.group("label").strip()
                when = matched.group("when").strip()
                temporal = self._normalizer.normalize(when, anchor_at=anchor_at)
                events.append(
                    TimelineEvent(
                        event_id=_new_id("hpi"),
                        event_type=EventType.SYMPTOM_ONGOING,
                        clinical_category=ClinicalCategory.SYMPTOM,
                        label=label,
                        temporal=temporal,
                        status=_status_for_temporal(
                            temporal.kind,
                            default=TemporalStatus.ONGOING,
                            recurring=temporal.recurring,
                        ),
                        source=EventSource.HPI,
                        evidence=(_evidence(EventSource.HPI, chief, source_ref="summary.chief_complaint"),),
                        confidence=0.85,
                    )
                )
            else:
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
                events.append(
                    TimelineEvent(
                        event_id=_new_id("hpi"),
                        event_type=EventType.SYMPTOM_ONGOING,
                        clinical_category=ClinicalCategory.SYMPTOM,
                        label=chief,
                        temporal=temporal,
                        status=TemporalStatus.ONGOING,
                        source=EventSource.HPI,
                        evidence=(_evidence(EventSource.HPI, chief, source_ref="summary.chief_complaint"),),
                        confidence=0.7,
                    )
                )

        if onset:
            temporal = self._normalizer.normalize(onset, anchor_at=anchor_at)
            label = chief or onset
            events.append(
                TimelineEvent(
                    event_id=_new_id("hpi_onset"),
                    event_type=EventType.SYMPTOM_ONSET,
                    clinical_category=ClinicalCategory.SYMPTOM,
                    label=label,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=EventSource.HPI,
                    evidence=(
                        _evidence(EventSource.HPI, onset, source_ref="summary.symptom_onset"),
                    ),
                    confidence=0.85,
                )
            )

        if notes and _TEMPORAL_HINT_RE.search(notes):
            for fragment in self._split_narrative_fragments(notes):
                events.extend(
                    self._events_from_narrative(
                        fragment,
                        source=EventSource.HPI,
                        source_ref="summary.additional_notes",
                        anchor_at=anchor_at,
                        default_category=ClinicalCategory.SYMPTOM,
                    )
                )

        for symptom in summary.symptoms or []:
            if not symptom or not symptom.strip():
                continue
            # Avoid duplicating chief complaint symptom labels
            if chief and symptom.strip().lower() in chief.lower():
                continue
            temporal_text = duration or None
            if _TEMPORAL_HINT_RE.search(symptom) or re.search(
                r"\b(every|each|weekly|daily|monthly|هفته‌ای)\b",
                symptom,
                re.IGNORECASE,
            ):
                temporal_text = symptom
            elif (summary.symptom_timing or "").strip():
                temporal_text = summary.symptom_timing
            temporal = self._normalizer.normalize(temporal_text, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("symptom"),
                    event_type=EventType.SYMPTOM_ONGOING,
                    clinical_category=ClinicalCategory.SYMPTOM,
                    label=symptom.strip(),
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=EventSource.HPI,
                    evidence=(
                        _evidence(
                            EventSource.HPI,
                            symptom.strip(),
                            source_ref="summary.symptoms",
                        ),
                    ),
                    confidence=0.75,
                )
            )

        return events

    def extract_pmh(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        overview = context.overview
        if overview:
            for condition in overview.chronic_conditions:
                duration = (condition.duration or "").strip()
                temporal = self._normalizer.normalize(duration or None, anchor_at=anchor_at)
                # "diagnosed in YYYY" style may live in name
                diagnosed = _DIAGNOSED_RE.match(condition.name.strip())
                if diagnosed:
                    label = diagnosed.group("label").strip()
                    when = diagnosed.group("when").strip()
                    temporal = self._normalizer.normalize(
                        f"diagnosed in {when}" if when.isdigit() else when,
                        anchor_at=anchor_at,
                    )
                    status = TemporalStatus.HISTORICAL
                    event_type = EventType.CONDITION_DIAGNOSED
                else:
                    label = condition.name.strip()
                    status = _status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING if duration else TemporalStatus.UNKNOWN,
                        recurring=temporal.recurring,
                    )
                    if temporal.kind == TemporalKind.ABSOLUTE:
                        status = TemporalStatus.HISTORICAL
                        event_type = EventType.CONDITION_DIAGNOSED
                    else:
                        event_type = EventType.CONDITION_DIAGNOSED

                events.append(
                    TimelineEvent(
                        event_id=_new_id("pmh"),
                        event_type=event_type,
                        clinical_category=ClinicalCategory.CONDITION,
                        label=label,
                        temporal=temporal,
                        status=status,
                        source=EventSource.PMH,
                        evidence=(
                            _evidence(
                                EventSource.PMH,
                                f"{condition.name} {duration}".strip(),
                                source_ref=condition.id,
                            ),
                        ),
                        confidence=0.9,
                    )
                )

        for assertion in context.pmh_assertions:
            detail = (assertion.detail or "").strip()
            concept = (assertion.concept or assertion.assertion_id or "").strip()
            if not concept:
                continue
            # Skip if already covered by overview chronic condition names
            if any(e.label.lower() == concept.lower() and e.source == EventSource.PMH for e in events):
                continue
            temporal = self._normalizer.normalize(detail or None, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("pmh_assert"),
                    event_type=EventType.CONDITION_DIAGNOSED,
                    clinical_category=ClinicalCategory.CONDITION,
                    label=concept,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING if detail else TemporalStatus.UNKNOWN,
                        recurring=temporal.recurring,
                    ),
                    source=EventSource.PMH,
                    evidence=(
                        _evidence(
                            EventSource.PMH,
                            f"{concept} {detail}".strip(),
                            source_ref=assertion.assertion_id,
                        ),
                    ),
                    confidence=0.8,
                )
            )

        # Free-text past medical history entries that look like diagnosed conditions
        for item in context.summary.past_medical_history or []:
            text = (item or "").strip()
            if not text:
                continue
            diagnosed = _DIAGNOSED_RE.match(text)
            if diagnosed:
                label = diagnosed.group("label").strip()
                when = diagnosed.group("when").strip()
                temporal = self._normalizer.normalize(
                    f"diagnosed in {when}" if re.fullmatch(r"\d{4}", when) else when,
                    anchor_at=anchor_at,
                )
            else:
                label = text
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("pmh_hist"),
                    event_type=EventType.CONDITION_DIAGNOSED,
                    clinical_category=ClinicalCategory.CONDITION,
                    label=label,
                    temporal=temporal,
                    status=(
                        TemporalStatus.HISTORICAL
                        if temporal.kind == TemporalKind.ABSOLUTE
                        else TemporalStatus.UNKNOWN
                    ),
                    source=EventSource.PMH,
                    evidence=(_evidence(EventSource.PMH, text, source_ref="summary.past_medical_history"),),
                    confidence=0.85,
                )
            )

        return events

    def extract_surgical(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        overview = context.overview
        if not overview or not (overview.surgical_history or "").strip():
            return []

        text = overview.surgical_history.strip()
        # Split on common delimiters while keeping unknown dates
        parts = [p.strip() for p in re.split(r"[;\n،]+", text) if p.strip()]
        events: list[TimelineEvent] = []
        for part in parts:
            # Try trailing year / date
            year_match = re.search(r"(19\d{2}|20\d{2})", part)
            if year_match:
                temporal = self._normalizer.normalize(year_match.group(1), anchor_at=anchor_at)
                label = part[: year_match.start()].strip(" -–,") or part
            else:
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
                label = part
            events.append(
                TimelineEvent(
                    event_id=_new_id("surg"),
                    event_type=EventType.PROCEDURE,
                    clinical_category=ClinicalCategory.PROCEDURE,
                    label=label,
                    temporal=temporal,
                    status=(
                        TemporalStatus.HISTORICAL
                        if temporal.kind != TemporalKind.UNKNOWN
                        else TemporalStatus.UNKNOWN
                    ),
                    source=EventSource.SURGICAL_HISTORY,
                    evidence=(
                        _evidence(
                            EventSource.SURGICAL_HISTORY,
                            part,
                            source_ref="overview.surgical_history",
                        ),
                    ),
                    confidence=0.8 if temporal.kind != TemporalKind.UNKNOWN else 0.5,
                )
            )
        return events

    def extract_medications(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []

        for med in context.medication_evidence:
            name = (med.name or "").strip()
            if not name:
                continue
            start_match = _MED_START_RE.match(name)
            freq = (med.frequency or "").strip()
            temporal_text = None
            event_type = EventType.MEDICATION_START
            if start_match:
                label = start_match.group("label").strip()
                temporal_text = start_match.group("when").strip()
            else:
                label = name
                # Look for temporal cues in amount/frequency fields
                for candidate in (med.amount, med.frequency):
                    if candidate and _TEMPORAL_HINT_RE.search(candidate):
                        temporal_text = candidate
                        break
                if freq and re.search(r"every|هر|هفته‌ای|daily|weekly", freq, re.IGNORECASE):
                    event_type = EventType.MEDICATION_CHANGE

            temporal = self._normalizer.normalize(temporal_text, anchor_at=anchor_at)
            status = _status_for_temporal(
                temporal.kind,
                default=TemporalStatus.ONGOING,
                recurring=temporal.recurring
                or bool(freq and re.search(r"every|هر|هفته‌ای", freq, re.IGNORECASE)),
            )
            if temporal.kind == TemporalKind.RELATIVE_PAST:
                event_type = EventType.MEDICATION_START
            events.append(
                TimelineEvent(
                    event_id=_new_id("med"),
                    event_type=event_type,
                    clinical_category=ClinicalCategory.MEDICATION,
                    label=label,
                    temporal=temporal,
                    status=status,
                    source=EventSource.MEDICATION,
                    evidence=(
                        _evidence(
                            EventSource.MEDICATION,
                            f"{name} {med.amount} {freq}".strip(),
                            source_ref=med.medication_id,
                        ),
                    ),
                    confidence=0.85,
                )
            )

        # Free-text current medications on summary
        for item in context.summary.current_medications or []:
            text = (item or "").strip()
            if not text:
                continue
            start_match = _MED_START_RE.match(text)
            if start_match:
                label = start_match.group("label").strip()
                when = start_match.group("when").strip()
                temporal = self._normalizer.normalize(when, anchor_at=anchor_at)
                event_type = EventType.MEDICATION_START
            else:
                label = text
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
                event_type = EventType.MEDICATION_START
            events.append(
                TimelineEvent(
                    event_id=_new_id("med_sum"),
                    event_type=event_type,
                    clinical_category=ClinicalCategory.MEDICATION,
                    label=label,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=EventSource.MEDICATION,
                    evidence=(
                        _evidence(
                            EventSource.MEDICATION,
                            text,
                            source_ref="summary.current_medications",
                        ),
                    ),
                    confidence=0.8,
                )
            )

        return events

    def extract_labs(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for lab in context.lab_evidence:
            name = (lab.name or "").strip() or "lab"
            extracted = (lab.extracted_data or "").strip()
            when_text = None
            upload_match = _UPLOAD_YESTERDAY_RE.search(extracted) if extracted else None
            if upload_match:
                when_text = upload_match.group("when")
            elif extracted and _TEMPORAL_HINT_RE.search(extracted):
                hint = _TEMPORAL_HINT_RE.search(extracted)
                when_text = hint.group(0) if hint else None

            temporal = self._normalizer.normalize(when_text, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("lab"),
                    event_type=EventType.LAB_RESULT,
                    clinical_category=ClinicalCategory.LABORATORY,
                    label=name,
                    temporal=temporal,
                    status=(
                        TemporalStatus.HISTORICAL
                        if temporal.kind != TemporalKind.UNKNOWN
                        else TemporalStatus.UNKNOWN
                    ),
                    source=EventSource.LABORATORY,
                    evidence=(
                        _evidence(
                            EventSource.LABORATORY,
                            extracted or name,
                            source_ref=lab.lab_id,
                        ),
                    ),
                    confidence=0.8 if when_text else 0.6,
                )
            )
        return events

    def extract_chat(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for idx, message in enumerate(context.chat_history):
            if message.role not in {"user", "patient"}:
                continue
            content = (message.content or "").strip()
            if not content or not _TEMPORAL_HINT_RE.search(content):
                continue
            msg_anchor = message.created_at or anchor_at
            for fragment in self._split_narrative_fragments(content):
                events.extend(
                    self._events_from_narrative(
                        fragment,
                        source=EventSource.CHAT,
                        source_ref=f"chat[{idx}]",
                        anchor_at=msg_anchor,
                        default_category=ClinicalCategory.CHAT,
                    )
                )
        return events

    def extract_documents(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for idx, analysis in enumerate(context.file_analyses):
            for lab in analysis.lab_results:
                label = (lab.test_name or "lab").strip()
                excerpt = f"{label} {lab.value or ''} {lab.unit or ''}".strip()
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
                events.append(
                    TimelineEvent(
                        event_id=_new_id("doc_lab"),
                        event_type=EventType.LAB_RESULT,
                        clinical_category=ClinicalCategory.LABORATORY,
                        label=label,
                        temporal=temporal,
                        status=TemporalStatus.UNKNOWN,
                        source=EventSource.DOCUMENT,
                        evidence=(
                            _evidence(
                                EventSource.DOCUMENT,
                                excerpt,
                                source_ref=f"file_analyses[{idx}]",
                            ),
                        ),
                        confidence=0.6,
                    )
                )
            for med in analysis.medications:
                label = (med.name or "").strip()
                if not label:
                    continue
                temporal = self._normalizer.normalize(None, anchor_at=anchor_at)
                events.append(
                    TimelineEvent(
                        event_id=_new_id("doc_med"),
                        event_type=EventType.MEDICATION_START,
                        clinical_category=ClinicalCategory.MEDICATION,
                        label=label,
                        temporal=temporal,
                        status=TemporalStatus.ONGOING,
                        source=EventSource.DOCUMENT,
                        evidence=(
                            _evidence(
                                EventSource.DOCUMENT,
                                label,
                                source_ref=f"file_analyses[{idx}]",
                            ),
                        ),
                        confidence=0.6,
                    )
                )
        return events

    def _split_narrative_fragments(self, text: str) -> list[str]:
        parts = re.split(r"[.\n;]+", text)
        return [p.strip() for p in parts if p.strip() and _TEMPORAL_HINT_RE.search(p)]

    def _events_from_narrative(
        self,
        fragment: str,
        *,
        source: EventSource,
        source_ref: str,
        anchor_at: datetime,
        default_category: ClinicalCategory,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []

        diagnosed = _DIAGNOSED_RE.search(fragment)
        if diagnosed:
            label = diagnosed.group("label").strip()
            when = diagnosed.group("when").strip()
            temporal = self._normalizer.normalize(
                f"diagnosed in {when}" if re.fullmatch(r"\d{4}", when) else when,
                anchor_at=anchor_at,
            )
            events.append(
                TimelineEvent(
                    event_id=_new_id("narr_dx"),
                    event_type=EventType.CONDITION_DIAGNOSED,
                    clinical_category=ClinicalCategory.CONDITION,
                    label=label,
                    temporal=temporal,
                    status=TemporalStatus.HISTORICAL,
                    source=source,
                    evidence=(_evidence(source, fragment, source_ref=source_ref),),
                    confidence=0.8,
                )
            )
            return events

        med = _MED_START_RE.search(fragment)
        if med:
            label = med.group("label").strip()
            when = med.group("when").strip()
            temporal = self._normalizer.normalize(when, anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("narr_med"),
                    event_type=EventType.MEDICATION_START,
                    clinical_category=ClinicalCategory.MEDICATION,
                    label=label,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=source,
                    evidence=(_evidence(source, fragment, source_ref=source_ref),),
                    confidence=0.8,
                )
            )
            return events

        for_match = _FOR_DURATION_RE.search(fragment)
        if for_match:
            label = for_match.group("label").strip()
            when = for_match.group("when").strip()
            temporal = self._normalizer.normalize(f"for {when}", anchor_at=anchor_at)
            events.append(
                TimelineEvent(
                    event_id=_new_id("narr_sym"),
                    event_type=EventType.SYMPTOM_ONGOING,
                    clinical_category=ClinicalCategory.SYMPTOM,
                    label=label,
                    temporal=temporal,
                    status=_status_for_temporal(
                        temporal.kind,
                        default=TemporalStatus.ONGOING,
                        recurring=temporal.recurring,
                    ),
                    source=source,
                    evidence=(_evidence(source, fragment, source_ref=source_ref),),
                    confidence=0.75,
                )
            )
            return events

        temporal = self._normalizer.normalize(fragment, anchor_at=anchor_at)
        if temporal.kind == TemporalKind.UNKNOWN and not temporal.recurring:
            return events

        events.append(
            TimelineEvent(
                event_id=_new_id("narr"),
                event_type=EventType.NARRATIVE,
                clinical_category=default_category,
                label=fragment[:120],
                temporal=temporal,
                status=_status_for_temporal(
                    temporal.kind,
                    default=TemporalStatus.UNKNOWN,
                    recurring=temporal.recurring,
                ),
                source=source,
                evidence=(_evidence(source, fragment, source_ref=source_ref),),
                confidence=0.6,
            )
        )
        return events
