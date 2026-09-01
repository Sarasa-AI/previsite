/**
 * Pure projection: ClinicalContentResponse → ClinicalContentViewModel.
 * Near-identity unwrap + snake_case → camelCase. No clinical logic.
 */

import type {
  ClinicalContentBodyDTO,
  ClinicalContentResponse,
  DocumentsContentDTO,
  HPIContentDTO,
  LabsContentDTO,
  MedicationsContentDTO,
  MissingInfoContentDTO,
  PatientHeaderContentDTO,
  RedFlagsContentDTO,
  SnapshotStripContentDTO,
  TimelineContentDTO,
} from "../../api/types";
import type { ClinicalContentViewModel } from "../../components/types";

export type ClinicalContentProjection = {
  readonly sessionId: number;
  readonly contextHash: string;
  readonly contentVersion: string;
  readonly generatedAt: string;
  readonly clinicalContent: ClinicalContentViewModel;
};

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
    allergyState: dto.allergy_state,
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
        catalogId: item.catalog_id ?? null,
        name: item.name,
        dose: item.dose,
        doseUnit: item.dose_unit ?? null,
        frequency: item.frequency,
        status: item.status,
        source: item.source,
        genericName: item.generic_name ?? null,
        brandName: item.brand_name ?? null,
        strength: item.strength ?? null,
        dosageForm: item.dosage_form ?? null,
        manufacturer: item.manufacturer ?? null,
        company: item.company ?? null,
        quantity: item.quantity ?? null,
        duration: item.duration ?? null,
        route: item.route ?? null,
        instructions: item.instructions ?? null,
        confidence: item.confidence ?? null,
        verificationStatus: item.verification_status ?? null,
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
      state: row.state,
      trend: row.trend,
      detail: row.detail,
      timestamp: row.timestamp,
      source: row.source,
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

function mapHPI(dto: HPIContentDTO | null) {
  if (!dto) return null;
  return {
    hpiSummary: dto.hpi_summary,
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
    hpi: mapHPI(content.hpi),
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

export function projectClinicalContentEnvelope(
  response: ClinicalContentResponse,
): ClinicalContentProjection {
  return {
    sessionId: response.session_id,
    contextHash: response.context_hash,
    contentVersion: response.content_version,
    generatedAt: response.generated_at,
    clinicalContent: mapBody(response.content),
  };
}
