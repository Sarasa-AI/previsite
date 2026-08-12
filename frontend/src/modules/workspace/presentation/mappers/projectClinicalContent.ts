/**
 * Pure projection: ClinicalContentResponse → ClinicalContentViewModel.
 * Near-identity unwrap + snake_case → camelCase. No clinical logic.
 */

import type {
  ClinicalContentBodyDTO,
  ClinicalContentResponse,
  DocumentsContentDTO,
  LabsContentDTO,
  MedicationsContentDTO,
  MissingInfoContentDTO,
  PatientHeaderContentDTO,
  RedFlagsContentDTO,
  SnapshotStripContentDTO,
  TimelineContentDTO,
} from "../../api/types";
import type { ClinicalContentViewModel } from "../../components/types";

function mapPatientHeader(dto: PatientHeaderContentDTO | null) {
  if (!dto) return null;
  return {
    name: dto.name,
    age: dto.age,
    sex: dto.sex,
    mrn: dto.mrn,
    visitType: dto.visit_type,
    status: dto.status,
  };
}

function mapRedFlags(dto: RedFlagsContentDTO | null) {
  if (!dto) return null;
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      title: item.title,
      severity: item.severity,
      explanation: item.explanation,
    })),
  };
}

function mapSnapshot(dto: SnapshotStripContentDTO | null) {
  if (!dto) return null;
  return {
    vitals: dto.vitals,
    problems: dto.problems,
    risk: dto.risk,
    allergies: dto.allergies,
    medicationCount: dto.medication_count,
    timelineCount: dto.timeline_count,
  };
}

function mapTimeline(dto: TimelineContentDTO | null) {
  if (!dto) return null;
  return {
    groups: dto.groups.map((group) => ({
      date: group.date,
      events: group.events.map((event) => ({
        id: event.id,
        title: event.title,
        detail: event.detail,
        source: event.source,
      })),
    })),
  };
}

function mapMedications(dto: MedicationsContentDTO | null) {
  if (!dto) return null;
  return {
    groups: dto.groups.map((group) => ({
      label: group.label,
      items: group.items.map((item) => ({
        id: item.id,
        name: item.name,
        dose: item.dose,
        frequency: item.frequency,
        status: item.status,
        source: item.source,
      })),
    })),
  };
}

function mapLabs(dto: LabsContentDTO | null) {
  if (!dto) return null;
  return {
    rows: dto.rows.map((row) => ({
      id: row.id,
      name: row.name,
      value: row.value,
      unit: row.unit,
      referenceRange: row.reference_range,
      abnormal: row.abnormal,
      trend: row.trend,
      detail: row.detail,
    })),
  };
}

function mapMissingInfo(dto: MissingInfoContentDTO | null) {
  if (!dto) return null;
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      label: item.label,
      priority: item.priority,
    })),
    actionLabel: dto.action_label,
  };
}

function mapDocuments(dto: DocumentsContentDTO | null) {
  if (!dto) return null;
  return {
    items: dto.items.map((item) => ({
      id: item.id,
      name: item.name,
      confidence: item.confidence,
      uploadedAt: item.uploaded_at,
      detail: item.detail,
    })),
  };
}

function mapBody(content: ClinicalContentBodyDTO): ClinicalContentViewModel {
  return {
    patientHeader: mapPatientHeader(content.patient_header),
    chiefComplaint: content.chief_complaint
      ? {
          title: content.chief_complaint.title,
          duration: content.chief_complaint.duration,
          priority: content.chief_complaint.priority,
        }
      : null,
    redFlags: mapRedFlags(content.red_flags),
    snapshot: mapSnapshot(content.snapshot),
    timeline: mapTimeline(content.timeline),
    medications: mapMedications(content.medications),
    labs: mapLabs(content.labs),
    missingInfo: mapMissingInfo(content.missing_info),
    soap: content.soap
      ? {
          assessment: content.soap.assessment,
          plan: content.soap.plan,
        }
      : null,
    documents: mapDocuments(content.documents),
  };
}

/**
 * Unwrap versioned envelope and map content into ClinicalContentViewModel.
 * Workspace consumes only the content object after mapping.
 */
export function projectClinicalContent(
  response: ClinicalContentResponse,
): ClinicalContentViewModel {
  return mapBody(response.content);
}
