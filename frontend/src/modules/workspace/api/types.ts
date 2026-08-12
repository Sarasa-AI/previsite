/**
 * Wire DTOs — strict mirrors of backend Workspace API contract
 * (`backend/app/modules/workspace/interface/dto.py`).
 *
 * These must never evolve independently of the backend contract.
 * Whenever the backend contract changes, regenerate or update these
 * definitions before any mapper or ViewModel changes.
 *
 * DTOs are contract objects only. They are not frontend domain models.
 */

export const WORKSPACE_CONTRACT_VERSION = "1.0.0";

/** Opaque wire strings — tolerate unknown values per API forward-compat. */
export type WireString = string;

export interface TrustDescriptorDTO {
  primary_provenance: WireString;
  all_provenance: WireString[];
  confidence: number | null;
  verification: WireString;
  evidence_refs: WireString[];
}

export interface LayoutDirectiveDTO {
  object_id: WireString;
  priority: WireString;
  slot: WireString;
  size: WireString;
  pinned: boolean;
  trust: TrustDescriptorDTO;
  flags: WireString[];
  visibility_reason: WireString | null;
}

export interface DecisionQueueItemDTO {
  rank: number;
  object_id: WireString;
  reason_code: WireString;
  explanation: string;
  acknowledge_required: boolean;
}

export interface CognitiveBudgetDTO {
  primary_count: number;
  expanded_count: number;
  deferred_count: number;
}

export interface ClinicalStoryDTO {
  text: string;
  confidence: number | null;
  evidence_refs: WireString[];
  stale: boolean;
}

export interface PlanMetadataDTO {
  context_hash: string;
  lens: WireString;
  role: WireString;
  computed_at: string;
  workspace_plan_version: string;
  generated_at: string;
  generated_by: string;
  compute_duration_ms: number;
}

export interface WorkspacePlanResponse {
  contract_version: string;
  session_id: number;
  workspace_state: WireString;
  layout_directives: LayoutDirectiveDTO[];
  decision_queue: DecisionQueueItemDTO[];
  story: ClinicalStoryDTO | null;
  pin_zone: WireString[];
  cognitive_budget: CognitiveBudgetDTO;
  metadata: PlanMetadataDTO;
  plan_etag: string;
}

export interface AcknowledgementRequest {
  object_id: string;
}

/** Additive wire DTO for GET .../workspace/story/status. */
export interface StoryStatusResponse {
  story_status: "ready" | "refresh_requested" | "generating" | "failed" | WireString;
  context_hash: string;
  stale: boolean;
  plan_etag: string | null;
}

export interface DecisionTraceStepDTO {
  object_id: WireString;
  step_label: string;
  priority_before: WireString | null;
  priority_after: WireString;
  detail: string;
}

export interface DecisionTraceResponse {
  session_id: number;
  trace_version: string;
  steps: DecisionTraceStepDTO[];
  plan_etag: string;
}

export type WorkspaceErrorCode =
  | "WORKSPACE_SESSION_NOT_FOUND"
  | "WORKSPACE_ACCESS_DENIED"
  | "WORKSPACE_LENS_UNKNOWN"
  | "WORKSPACE_ROLE_UNKNOWN"
  | "WORKSPACE_OBJECT_UNKNOWN"
  | "WORKSPACE_PLAN_STALE"
  | "WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE"
  | "WORKSPACE_OBJECT_NOT_RESOLVABLE"
  | "WORKSPACE_OBJECT_NOT_DISMISSIBLE"
  | "WORKSPACE_READ_ONLY"
  | "WORKSPACE_TRACE_DISABLED"
  | "WORKSPACE_COMPUTE_FAILED";

export interface WorkspaceErrorEnvelope {
  success: false;
  detail: string;
  error?: {
    status_code: number;
    message: string;
    path: string;
    timestamp: string;
  };
}

export interface WorkspaceQueryParams {
  lens?: string;
  role?: string;
  offline?: boolean;
}

export type WorkspacePlanResult =
  | {
      notModified: false;
      plan: WorkspacePlanResponse;
      etag: string;
      contractVersion: string;
      requestId: string | null;
    }
  | {
      notModified: true;
      etag: string;
      contractVersion: string | null;
      requestId: string | null;
    };

/** Clinical content presentation contract version (backend CONTENT_VERSION). */
export const CLINICAL_CONTENT_VERSION = "1.0.0";

export type ClinicalContentSeverity = "critical" | "warning" | "info";
export type ClinicalContentTrend = "up" | "down" | "stable" | "unknown";

export interface PatientHeaderContentDTO {
  name: string;
  age: number;
  sex: string;
  mrn: string;
  visit_type: string;
  status: string;
}

export interface ChiefComplaintContentDTO {
  title: string;
  duration: string;
  priority: string;
}

export interface RedFlagItemDTO {
  id: string;
  title: string;
  severity: ClinicalContentSeverity;
  explanation: string;
}

export interface RedFlagsContentDTO {
  items: RedFlagItemDTO[];
}

export interface SnapshotStripContentDTO {
  vitals: string;
  problems: string;
  risk: string;
  allergies: string;
  medication_count: number;
  timeline_count: number;
}

export interface TimelineEventContentDTO {
  id: string;
  title: string;
  detail: string;
  source: string;
}

export interface TimelineGroupContentDTO {
  date: string;
  events: TimelineEventContentDTO[];
}

export interface TimelineContentDTO {
  groups: TimelineGroupContentDTO[];
}

export interface MedicationItemDTO {
  id: string;
  name: string;
  dose: string;
  frequency: string;
  status: string;
  source: string;
}

export interface MedicationGroupDTO {
  label: string;
  items: MedicationItemDTO[];
}

export interface MedicationsContentDTO {
  groups: MedicationGroupDTO[];
}

export interface LabRowDTO {
  id: string;
  name: string;
  value: string;
  unit: string;
  reference_range: string;
  abnormal: boolean;
  trend: ClinicalContentTrend;
  detail: string;
}

export interface LabsContentDTO {
  rows: LabRowDTO[];
}

export interface MissingInfoItemDTO {
  id: string;
  label: string;
  priority: string;
}

export interface MissingInfoContentDTO {
  items: MissingInfoItemDTO[];
  action_label: string;
}

export interface SoapContentDTO {
  assessment: string;
  plan: string;
}

export interface DocumentItemDTO {
  id: string;
  name: string;
  confidence: number | "unknown";
  uploaded_at: string;
  detail: string;
}

export interface DocumentsContentDTO {
  items: DocumentItemDTO[];
}

export interface ClinicalContentBodyDTO {
  patient_header: PatientHeaderContentDTO | null;
  chief_complaint: ChiefComplaintContentDTO | null;
  red_flags: RedFlagsContentDTO | null;
  snapshot: SnapshotStripContentDTO | null;
  timeline: TimelineContentDTO | null;
  medications: MedicationsContentDTO | null;
  labs: LabsContentDTO | null;
  missing_info: MissingInfoContentDTO | null;
  soap: SoapContentDTO | null;
  documents: DocumentsContentDTO | null;
}

/** Versioned transport envelope from GET .../clinical-content. */
export interface ClinicalContentResponse {
  session_id: number;
  context_hash: string;
  content_version: string;
  generated_at: string;
  content: ClinicalContentBodyDTO;
}
