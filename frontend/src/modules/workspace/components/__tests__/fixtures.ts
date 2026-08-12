import type { TrustViewModel } from "../../presentation/viewmodels/types";
import type {
  ChiefComplaintContent,
  DocumentsContent,
  LabsContent,
  MedicationsContent,
  MissingInfoContent,
  PatientHeaderContent,
  RedFlagsContent,
  SnapshotStripContent,
  SoapContent,
  TimelineContent,
} from "../types";

export const trustFixture: TrustViewModel = Object.freeze({
  primaryProvenance: "ehr",
  allProvenance: Object.freeze(["ehr", "patient_report"]),
  confidence: 0.92,
  verification: "verified",
  evidenceRefs: Object.freeze(["ev-1"]),
});

export const patientHeaderFixture: PatientHeaderContent = Object.freeze({
  name: "Jane Doe",
  age: 54,
  sex: "F",
  mrn: "MRN-10042",
  visitType: "Follow-up",
  status: "Arrived",
});

export const chiefComplaintFixture: ChiefComplaintContent = Object.freeze({
  title: "Chest tightness",
  duration: "3 days",
  priority: "p1",
});

export const redFlagsFixture: RedFlagsContent = Object.freeze({
  items: Object.freeze([
    Object.freeze({
      id: "rf-1",
      title: "Exertional dyspnea",
      severity: "critical" as const,
      explanation: "Worsening with mild activity; rule out ACS.",
    }),
    Object.freeze({
      id: "rf-2",
      title: "Recent syncope",
      severity: "warning" as const,
      explanation: "Single episode yesterday; no head trauma.",
    }),
  ]),
});

export const snapshotStripFixture: SnapshotStripContent = Object.freeze({
  vitals: "BP 138/86 · HR 88",
  problems: "HTN, T2DM",
  risk: "Moderate CV",
  allergies: "Penicillin",
  medicationCount: 4,
  timelineCount: 12,
});

export const timelineFixture: TimelineContent = Object.freeze({
  groups: Object.freeze([
    Object.freeze({
      date: "2026-08-01",
      events: Object.freeze([
        Object.freeze({
          id: "te-1",
          title: "ED visit",
          detail: "Presented with chest tightness; troponin pending.",
          source: "ehr",
        }),
      ]),
    }),
    Object.freeze({
      date: "2026-07-20",
      events: Object.freeze([
        Object.freeze({
          id: "te-2",
          title: "Primary care visit",
          detail: "BP elevated; meds adjusted.",
          source: "clinic_note",
        }),
      ]),
    }),
  ]),
});

export const medicationsFixture: MedicationsContent = Object.freeze({
  groups: Object.freeze([
    Object.freeze({
      label: "Cardiovascular",
      items: Object.freeze([
        Object.freeze({
          id: "med-1",
          name: "Lisinopril",
          dose: "10 mg",
          frequency: "daily",
          status: "active",
          source: "ehr",
        }),
      ]),
    }),
    Object.freeze({
      label: "Endocrine",
      items: Object.freeze([
        Object.freeze({
          id: "med-2",
          name: "Metformin",
          dose: "500 mg",
          frequency: "BID",
          status: "active",
          source: "patient_report",
        }),
      ]),
    }),
  ]),
});

export const labsFixture: LabsContent = Object.freeze({
  rows: Object.freeze([
    Object.freeze({
      id: "lab-1",
      name: "Troponin I",
      value: "0.08",
      unit: "ng/mL",
      referenceRange: "<0.04",
      abnormal: true,
      trend: "up" as const,
      detail: "Rising vs prior 0.03 (2026-07-01).",
    }),
    Object.freeze({
      id: "lab-2",
      name: "Creatinine",
      value: "0.9",
      unit: "mg/dL",
      referenceRange: "0.6–1.2",
      abnormal: false,
      trend: "stable" as const,
      detail: "Within reference range.",
    }),
  ]),
});

export const missingInfoFixture: MissingInfoContent = Object.freeze({
  items: Object.freeze([
    Object.freeze({
      id: "mi-1",
      label: "Last ECG date",
      priority: "p1",
    }),
    Object.freeze({
      id: "mi-2",
      label: "Smoking status",
      priority: "p2",
    }),
  ]),
  actionLabel: "Request update",
});

export const soapFixture: SoapContent = Object.freeze({
  assessment: "Likely unstable angina vs non-STEMI; risk stratified.",
  plan: "Serial troponins, ECG, ASA, cardiology consult.",
});

export const documentsFixture: DocumentsContent = Object.freeze({
  items: Object.freeze([
    Object.freeze({
      id: "doc-1",
      name: "ED triage note.pdf",
      confidence: 0.88,
      uploadedAt: "2026-08-01T14:22:00Z",
      detail: "Extracted vitals and chief complaint.",
    }),
    Object.freeze({
      id: "doc-2",
      name: "Prior ECG.png",
      confidence: "unknown" as const,
      uploadedAt: "2026-07-15T09:00:00Z",
      detail: "Image uploaded; OCR pending.",
    }),
  ]),
});
