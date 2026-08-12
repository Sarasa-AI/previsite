/**
 * Golden Clinical Dataset
 *
 * Architectural regression reference for Doctor Workspace contract validation.
 * NOT a performance benchmark.
 *
 * Future validation compares the rendered pipeline against this canonical dataset.
 * The dataset must remain stable. Intentional changes require an Architecture Gate
 * version bump (see docs/architecture/doctor-workspace-architecture-gate.md).
 */

import type { WorkspacePlanResponse } from "../api/types";
import type { ClinicalContentViewModel } from "../components/types";
import { makeDirective, makeTrust } from "./fixtures";
import {
  emptyClinicalContent,
  largeClinicalContent,
  partialClinicalContent,
} from "../components/__tests__/clinicalDatasets";

function freezeDeep<T>(value: T): T {
  if (value !== null && typeof value === "object") {
    Object.freeze(value);
    for (const child of Object.values(value as Record<string, unknown>)) {
      freezeDeep(child);
    }
  }
  return value;
}

/**
 * Canonical clinical content aggregate — realistic patient Margaret Chen.
 * Reuses the large representative dataset as the single source of truth.
 */
export const GOLDEN_CLINICAL_CONTENT: ClinicalContentViewModel = largeClinicalContent;

/** Stable narrative strings asserted verbatim by semantic/narrative tests. */
export const GOLDEN_NARRATIVE = {
  storyText:
    "67F with CAD and diabetes presents with 3 days of exertional chest tightness and dyspnea. Prior NSTEMI in 2023. Associated diaphoresis; recent syncope.",
  chiefComplaintTitle: GOLDEN_CLINICAL_CONTENT.chiefComplaint!.title,
  soapAssessment: GOLDEN_CLINICAL_CONTENT.soap!.assessment,
  soapPlan: GOLDEN_CLINICAL_CONTENT.soap!.plan,
  patientName: GOLDEN_CLINICAL_CONTENT.patientHeader!.name,
} as const;

/**
 * Canonical WorkspacePlanResponse aligned with GOLDEN_CLINICAL_CONTENT.
 * Includes all 16 catalog object_ids with deterministic slots/priorities/trust.
 */
export const GOLDEN_WORKSPACE_PLAN: WorkspacePlanResponse = freezeDeep({
  contract_version: "1.0.0",
  session_id: 884201,
  workspace_state: "review_needed",
  layout_directives: [
    makeDirective({
      object_id: "critical_alerts",
      slot: "pin",
      priority: "p0",
      size: "expanded",
      pinned: true,
      trust: makeTrust({
        primary_provenance: "system_derived",
        confidence: 0.95,
        verification: "verified",
        evidence_refs: ["ev-alert-1"],
      }),
    }),
    makeDirective({
      object_id: "red_flags",
      slot: "pin",
      priority: "p0",
      size: "expanded",
      pinned: true,
      trust: makeTrust({
        primary_provenance: "patient_reported",
        confidence: 0.88,
        verification: "partially_verified",
        evidence_refs: ["ev-rf-1"],
      }),
    }),
    makeDirective({
      object_id: "allergies",
      slot: "pin",
      priority: "p0",
      size: "badge",
      pinned: true,
      trust: makeTrust({
        primary_provenance: "document_ocr",
        confidence: 0.92,
        verification: "verified",
        evidence_refs: ["ev-allergy-1"],
      }),
    }),
    makeDirective({
      object_id: "chief_complaint",
      slot: "primary",
      priority: "p0",
      size: "expanded",
      pinned: false,
      trust: makeTrust({
        primary_provenance: "patient_reported",
        confidence: 0.9,
        verification: "verified",
        evidence_refs: ["ev-cc-1"],
      }),
    }),
    makeDirective({
      object_id: "timeline",
      slot: "primary",
      priority: "p1",
      size: "expanded",
      trust: makeTrust({ confidence: 0.85, evidence_refs: ["ev-tl-1"] }),
    }),
    makeDirective({
      object_id: "labs",
      slot: "primary",
      priority: "p1",
      size: "standard",
      trust: makeTrust({
        primary_provenance: "document_ocr",
        confidence: 0.87,
        evidence_refs: ["ev-lab-1"],
      }),
    }),
    makeDirective({
      object_id: "medications",
      slot: "primary",
      priority: "p2",
      size: "standard",
      trust: makeTrust({ confidence: 0.8, evidence_refs: ["ev-med-1"] }),
    }),
    makeDirective({
      object_id: "story",
      slot: "primary",
      priority: "p1",
      size: "standard",
      trust: makeTrust({
        primary_provenance: "ai_generated",
        confidence: 0.78,
        verification: "unverified",
        evidence_refs: ["ev-story-1"],
      }),
    }),
    makeDirective({
      object_id: "missing_data",
      slot: "secondary",
      priority: "p2",
      size: "standard",
      trust: makeTrust({ confidence: null, verification: "n/a", evidence_refs: ["ev-mi-1"] }),
    }),
    makeDirective({
      object_id: "soap",
      slot: "secondary",
      priority: "p2",
      size: "expanded",
      trust: makeTrust({
        primary_provenance: "ai_generated",
        confidence: 0.7,
        verification: "unverified",
        evidence_refs: ["ev-soap-1"],
      }),
    }),
    makeDirective({
      object_id: "snapshot",
      slot: "secondary",
      priority: "p2",
      size: "compressed",
      trust: makeTrust({ confidence: 0.91, evidence_refs: ["ev-snap-1"] }),
    }),
    makeDirective({
      object_id: "documents",
      slot: "deferred",
      priority: "p3",
      size: "compressed",
      trust: makeTrust({
        primary_provenance: "document_ocr",
        confidence: 0.75,
        evidence_refs: ["ev-doc-1"],
      }),
    }),
    makeDirective({
      object_id: "pmh",
      slot: "deferred",
      priority: "p3",
      size: "compressed",
      trust: makeTrust({ confidence: 0.82, evidence_refs: ["ev-pmh-1"] }),
    }),
    makeDirective({
      object_id: "patient_questions",
      slot: "deferred",
      priority: "p3",
      size: "compressed",
      trust: makeTrust({
        primary_provenance: "patient_reported",
        confidence: 0.6,
        evidence_refs: ["ev-pq-1"],
      }),
    }),
    makeDirective({
      object_id: "conflicts",
      slot: "hidden",
      priority: "p3",
      size: "compressed",
      pinned: false,
      visibility_reason: "no_data",
      trust: makeTrust({ confidence: null, verification: "n/a" }),
    }),
    makeDirective({
      object_id: "critical_labs",
      slot: "hidden",
      priority: "p3",
      size: "compressed",
      pinned: false,
      visibility_reason: "no_data",
      trust: makeTrust({ confidence: null, verification: "n/a" }),
    }),
  ],
  decision_queue: [
    {
      rank: 1,
      object_id: "critical_alerts",
      reason_code: "SAFETY",
      explanation: "Review critical alerts before proceeding",
      acknowledge_required: true,
    },
    {
      rank: 2,
      object_id: "red_flags",
      reason_code: "SAFETY",
      explanation: "Acknowledge red flags for ACS risk",
      acknowledge_required: true,
    },
    {
      rank: 3,
      object_id: "chief_complaint",
      reason_code: "ORIENT",
      explanation: "Confirm visit orientation: chief complaint",
      acknowledge_required: false,
    },
  ],
  story: {
    text: GOLDEN_NARRATIVE.storyText,
    confidence: 0.78,
    evidence_refs: ["ev-story-1", "summary.chief_complaint"],
    stale: false,
  },
  pin_zone: ["critical_alerts", "red_flags", "allergies"],
  cognitive_budget: {
    primary_count: 5,
    expanded_count: 2,
    deferred_count: 3,
  },
  metadata: {
    context_hash: "golden-context-hash-v1",
    lens: "general_medicine",
    role: "doctor",
    computed_at: "2026-07-28T15:00:00Z",
    workspace_plan_version: "1.0.0",
    generated_at: "2026-07-28T15:00:00Z",
    generated_by: "workspace-orchestrator@1.0.0",
    compute_duration_ms: 18,
  },
  plan_etag: "golden-etag-v1",
});

/** Catalog object_ids expected in the golden plan (all 16). */
export const GOLDEN_OBJECT_IDS = [
  "chief_complaint",
  "red_flags",
  "critical_alerts",
  "conflicts",
  "allergies",
  "timeline",
  "story",
  "labs",
  "critical_labs",
  "medications",
  "pmh",
  "documents",
  "patient_questions",
  "missing_data",
  "soap",
  "snapshot",
] as const;

/** Companion null/partial datasets for edge validation (not the golden reference). */
export const GOLDEN_PARTIAL_CLINICAL_CONTENT = partialClinicalContent;
export const GOLDEN_EMPTY_CLINICAL_CONTENT = emptyClinicalContent;
