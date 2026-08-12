/**
 * Pure projection: WorkspacePlanResponse → WorkspaceViewModel.
 * No React, no rendering, no business/clinical logic.
 */

import type { LayoutDirectiveDTO, WorkspacePlanResponse } from "../../api/types";
import { emitWorkspaceTelemetry } from "@/src/shared/utils/telemetry";
import type {
  CardViewModel,
  ConfidenceDisplay,
  RenderableSlot,
  TrustViewModel,
  WorkspaceViewModel,
} from "../viewmodels/types";

const RENDERABLE_SLOTS = new Set<RenderableSlot>(["pin", "primary", "secondary", "deferred"]);
const KNOWN_PRIORITIES = new Set(["p0", "p1", "p2", "p3"]);
const KNOWN_SIZES = new Set(["expanded", "standard", "compressed", "badge"]);

const CURRENTLY_SUPPORTED_OBJECT_IDS = new Set([
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
]);

function toConfidenceDisplay(confidence: number | null): ConfidenceDisplay {
  return confidence === null ? "unknown" : confidence;
}

function mapTrust(
  trust: LayoutDirectiveDTO["trust"],
): TrustViewModel {
  return {
    primaryProvenance: trust.primary_provenance,
    allProvenance: Object.freeze([...trust.all_provenance]),
    confidence: toConfidenceDisplay(trust.confidence),
    verification: trust.verification,
    evidenceRefs: Object.freeze([...trust.evidence_refs]),
  };
}

function isRenderableSlot(slot: string): slot is RenderableSlot {
  return RENDERABLE_SLOTS.has(slot as RenderableSlot);
}

function mapCard(
  directive: LayoutDirectiveDTO,
  sessionId: number,
  planEtag: string,
  contractVersion: string,
): CardViewModel | null {
  if (!CURRENTLY_SUPPORTED_OBJECT_IDS.has(directive.object_id)) {
    emitWorkspaceTelemetry("workspace.unknown_object_id", {
      object_id: directive.object_id,
      session_id: sessionId,
      plan_etag: planEtag,
      contract_version: contractVersion,
    });
    return null;
  }

  if (!isRenderableSlot(directive.slot)) {
    if (directive.slot !== "hidden") {
      emitWorkspaceTelemetry("workspace.unknown_enum", {
        field: "slot",
        value: directive.slot,
        object_id: directive.object_id,
        session_id: sessionId,
        plan_etag: planEtag,
        contract_version: contractVersion,
      });
    }
    return null;
  }

  if (!KNOWN_PRIORITIES.has(directive.priority)) {
    emitWorkspaceTelemetry("workspace.unknown_enum", {
      field: "priority",
      value: directive.priority,
      object_id: directive.object_id,
      session_id: sessionId,
      plan_etag: planEtag,
      contract_version: contractVersion,
    });
    return null;
  }

  if (!KNOWN_SIZES.has(directive.size)) {
    emitWorkspaceTelemetry("workspace.unknown_enum", {
      field: "size",
      value: directive.size,
      object_id: directive.object_id,
      session_id: sessionId,
      plan_etag: planEtag,
      contract_version: contractVersion,
    });
    return null;
  }

  return {
    objectId: directive.object_id,
    priority: directive.priority,
    slot: directive.slot,
    size: directive.size,
    pinned: directive.pinned,
    trust: mapTrust(directive.trust),
    flags: Object.freeze([...directive.flags]),
  };
}

function orderPinCards(
  pinZone: readonly string[],
  pinCards: CardViewModel[],
): CardViewModel[] {
  const byId = new Map(pinCards.map((card) => [card.objectId, card]));
  const ordered: CardViewModel[] = [];
  const seen = new Set<string>();

  for (const objectId of pinZone) {
    const card = byId.get(objectId);
    if (card) {
      ordered.push(card);
      seen.add(objectId);
    }
  }

  for (const card of pinCards) {
    if (!seen.has(card.objectId)) {
      ordered.push(card);
    }
  }

  return ordered;
}

function mutationsAllowedForState(workspaceState: string): boolean {
  return workspaceState !== "loading" && workspaceState !== "read_only" && workspaceState !== "offline";
}

/**
 * Project one immutable plan snapshot into an ephemeral ViewModel.
 * Never merge fragments from different ETags — caller replaces entirely.
 */
export function projectPlan(dto: WorkspacePlanResponse, etag: string): WorkspaceViewModel {
  const planEtag = etag || dto.plan_etag;
  const cards: CardViewModel[] = [];

  for (const directive of dto.layout_directives) {
    if (directive.slot === "hidden") {
      continue;
    }
    const card = mapCard(directive, dto.session_id, planEtag, dto.contract_version);
    if (card) cards.push(card);
  }

  const pinCards = orderPinCards(
    dto.pin_zone,
    cards.filter((c) => c.slot === "pin"),
  );

  const story =
    dto.story === null
      ? null
      : {
          text: dto.story.text,
          confidence: toConfidenceDisplay(dto.story.confidence),
          evidenceRefs: Object.freeze([...dto.story.evidence_refs]),
          stale: dto.story.stale,
        };

  return Object.freeze({
    sessionId: dto.session_id,
    workspaceState: dto.workspace_state,
    planEtag,
    contractVersion: dto.contract_version,
    pinCards: Object.freeze(pinCards),
    primaryCards: Object.freeze(cards.filter((c) => c.slot === "primary")),
    secondaryCards: Object.freeze(cards.filter((c) => c.slot === "secondary")),
    deferredCards: Object.freeze(cards.filter((c) => c.slot === "deferred")),
    queue: Object.freeze(
      dto.decision_queue.map((item) =>
        Object.freeze({
          rank: item.rank,
          objectId: item.object_id,
          reasonCode: item.reason_code,
          explanation: item.explanation,
          acknowledgeRequired: item.acknowledge_required,
        }),
      ),
    ),
    story: story ? Object.freeze(story) : null,
    cognitiveBudget: Object.freeze({
      primaryCount: dto.cognitive_budget.primary_count,
      expandedCount: dto.cognitive_budget.expanded_count,
      deferredCount: dto.cognitive_budget.deferred_count,
    }),
    metadata: Object.freeze({
      contextHash: dto.metadata.context_hash,
      lens: dto.metadata.lens,
      role: dto.metadata.role,
      computedAt: dto.metadata.computed_at,
      workspacePlanVersion: dto.metadata.workspace_plan_version,
      generatedAt: dto.metadata.generated_at,
      generatedBy: dto.metadata.generated_by,
      computeDurationMs: dto.metadata.compute_duration_ms,
    }),
    mutationsAllowed: mutationsAllowedForState(dto.workspace_state),
  });
}

export { CURRENTLY_SUPPORTED_OBJECT_IDS };
