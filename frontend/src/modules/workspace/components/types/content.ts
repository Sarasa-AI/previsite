/**
 * Component-layer content ViewModels.
 * Clinical/display fields only — never embed TrustViewModel or plan chrome.
 */

export type SeverityLevel = "critical" | "warning" | "info";

export type TrendDirection = "up" | "down" | "stable" | "unknown";

export interface PatientHeaderContent {
  readonly name: string;
  readonly age: number;
  readonly sex: string;
  readonly mrn: string;
  readonly visitType: string;
  readonly status: string;
}

export interface ChiefComplaintContent {
  readonly title: string;
  readonly duration: string;
  readonly priority: string;
}

export interface RedFlagItem {
  readonly id: string;
  readonly title: string;
  readonly severity: SeverityLevel;
  readonly explanation: string;
}

export interface RedFlagsContent {
  readonly items: readonly RedFlagItem[];
}

export interface SnapshotStripContent {
  readonly vitals: string;
  readonly problems: string;
  readonly risk: string;
  readonly allergies: string;
  readonly medicationCount: number;
  readonly timelineCount: number;
}

export interface TimelineEvent {
  readonly id: string;
  readonly title: string;
  readonly detail: string;
  readonly source: string;
}

export interface TimelineGroup {
  readonly date: string;
  readonly events: readonly TimelineEvent[];
}

export interface TimelineContent {
  readonly groups: readonly TimelineGroup[];
}

export interface MedicationItem {
  readonly id: string;
  readonly name: string;
  readonly dose: string;
  readonly frequency: string;
  readonly status: string;
  readonly source: string;
}

export interface MedicationGroup {
  readonly label: string;
  readonly items: readonly MedicationItem[];
}

export interface MedicationsContent {
  readonly groups: readonly MedicationGroup[];
}

export interface LabRow {
  readonly id: string;
  readonly name: string;
  readonly value: string;
  readonly unit: string;
  readonly referenceRange: string;
  readonly abnormal: boolean;
  readonly trend: TrendDirection;
  readonly detail: string;
}

export interface LabsContent {
  readonly rows: readonly LabRow[];
}

export interface MissingInfoItem {
  readonly id: string;
  readonly label: string;
  readonly priority: string;
}

export interface MissingInfoContent {
  readonly items: readonly MissingInfoItem[];
  readonly actionLabel: string;
}

export interface SoapContent {
  readonly assessment: string;
  readonly plan: string;
}

export interface DocumentItem {
  readonly id: string;
  readonly name: string;
  readonly confidence: number | "unknown";
  readonly uploadedAt: string;
  readonly detail: string;
}

export interface DocumentsContent {
  readonly items: readonly DocumentItem[];
}

export interface EmptyStateContent {
  readonly title: string;
  readonly message: string;
}

export interface ErrorStateContent {
  readonly title: string;
  readonly message: string;
}

/**
 * Presentation Integration Aggregate — NOT a domain model.
 * Groups existing content ViewModels for Shell composition only.
 * Owns no business rules or domain behavior.
 * May later be decomposed into feature-specific aggregates without
 * changing Presentation contracts (presenters already take slices).
 */
export interface ClinicalContentViewModel {
  readonly patientHeader: PatientHeaderContent | null;
  readonly chiefComplaint: ChiefComplaintContent | null;
  readonly redFlags: RedFlagsContent | null;
  readonly snapshot: SnapshotStripContent | null;
  readonly timeline: TimelineContent | null;
  readonly medications: MedicationsContent | null;
  readonly labs: LabsContent | null;
  readonly missingInfo: MissingInfoContent | null;
  readonly soap: SoapContent | null;
  readonly documents: DocumentsContent | null;
}

/** Union of feature body slices injectable into card presenters (never the aggregate). */
export type CardBodyContent =
  | ChiefComplaintContent
  | RedFlagsContent
  | SnapshotStripContent
  | TimelineContent
  | MedicationsContent
  | LabsContent
  | MissingInfoContent
  | SoapContent
  | DocumentsContent;
