import type {
  LayoutDirectiveDTO,
  TrustDescriptorDTO,
  WorkspacePlanResponse,
} from "../api/types";

export function makeTrust(overrides: Partial<TrustDescriptorDTO> = {}): TrustDescriptorDTO {
  return {
    primary_provenance: "system_derived",
    all_provenance: ["system_derived"],
    confidence: 0.9,
    verification: "verified",
    evidence_refs: ["ev-1"],
    ...overrides,
  };
}

export function makeDirective(
  overrides: Partial<LayoutDirectiveDTO> & Pick<LayoutDirectiveDTO, "object_id" | "slot">,
): LayoutDirectiveDTO {
  return {
    priority: "p1",
    size: "standard",
    pinned: overrides.slot === "pin",
    trust: makeTrust(),
    flags: [],
    visibility_reason: null,
    ...overrides,
  };
}

export function makePlan(
  overrides: Partial<WorkspacePlanResponse> = {},
): WorkspacePlanResponse {
  return {
    contract_version: "1.0.0",
    session_id: 42,
    workspace_state: "verified",
    layout_directives: [
      makeDirective({ object_id: "critical_alerts", slot: "pin", priority: "p0", size: "expanded", pinned: true }),
      makeDirective({ object_id: "chief_complaint", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "pmh", slot: "secondary", priority: "p2", size: "compressed" }),
      makeDirective({ object_id: "documents", slot: "deferred", priority: "p3", size: "compressed" }),
      makeDirective({
        object_id: "labs",
        slot: "hidden",
        priority: "p3",
        visibility_reason: "cognitive_budget",
      }),
    ],
    decision_queue: [
      {
        rank: 1,
        object_id: "critical_alerts",
        reason_code: "SAFETY",
        explanation: "Review critical alerts",
        acknowledge_required: true,
      },
    ],
    story: {
      text: "Patient presents with headache.",
      confidence: null,
      evidence_refs: ["ev-story"],
      stale: false,
    },
    pin_zone: ["critical_alerts"],
    cognitive_budget: {
      primary_count: 1,
      expanded_count: 1,
      deferred_count: 1,
    },
    metadata: {
      context_hash: "abc",
      lens: "general_medicine",
      role: "doctor",
      computed_at: "2026-07-28T14:30:00Z",
      workspace_plan_version: "1.0.0",
      generated_at: "2026-07-28T14:30:00Z",
      generated_by: "workspace-orchestrator@1.0.0",
      compute_duration_ms: 12,
    },
    plan_etag: "etag-v1",
    ...overrides,
  };
}
