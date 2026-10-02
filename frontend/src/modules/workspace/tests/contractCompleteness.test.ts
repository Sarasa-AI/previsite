/**
 * Contract completeness — field survival across DTO → projectPlan → ViewModel.
 * Complements semantic invariant tests; does not replace them.
 */

import { describe, expect, it } from "vitest";
import { projectPlan } from "../presentation/mappers/projectPlan";
import { GOLDEN_WORKSPACE_PLAN } from "./goldenClinicalDataset";

describe("Contract completeness: DTO → ViewModel", () => {
  const dto = GOLDEN_WORKSPACE_PLAN;
  const vm = projectPlan(dto, dto.plan_etag);

  it("top-level plan fields survive projection without unexpected renames", () => {
    expect(vm.sessionId).toBe(dto.session_id);
    expect(vm.workspaceState).toBe(dto.workspace_state);
    expect(vm.planEtag).toBe(dto.plan_etag);
    expect(vm.contractVersion).toBe(dto.contract_version);
  });

  it("cognitive budget and metadata fields survive", () => {
    expect(vm.cognitiveBudget.primaryCount).toBe(dto.cognitive_budget.primary_count);
    expect(vm.cognitiveBudget.expandedCount).toBe(dto.cognitive_budget.expanded_count);
    expect(vm.cognitiveBudget.deferredCount).toBe(dto.cognitive_budget.deferred_count);

    expect(vm.metadata.contextHash).toBe(dto.metadata.context_hash);
    expect(vm.metadata.lens).toBe(dto.metadata.lens);
    expect(vm.metadata.role).toBe(dto.metadata.role);
    expect(vm.metadata.computedAt).toBe(dto.metadata.computed_at);
    expect(vm.metadata.workspacePlanVersion).toBe(dto.metadata.workspace_plan_version);
    expect(vm.metadata.generatedAt).toBe(dto.metadata.generated_at);
    expect(vm.metadata.generatedBy).toBe(dto.metadata.generated_by);
    expect(vm.metadata.computeDurationMs).toBe(dto.metadata.compute_duration_ms);
  });

  it("queue item fields survive with stable semantic mapping", () => {
    expect(vm.queue).toHaveLength(dto.decision_queue.length);
    for (let i = 0; i < dto.decision_queue.length; i += 1) {
      const src = dto.decision_queue[i]!;
      const dest = vm.queue[i]!;
      expect(dest.rank).toBe(src.rank);
      expect(dest.objectId).toBe(src.object_id);
      expect(dest.reasonCode).toBe(src.reason_code);
      expect(dest.explanation).toBe(src.explanation);
      expect(dest.acknowledgeRequired).toBe(src.acknowledge_required);
    }
  });

  it("card chrome fields survive for every visible directive", () => {
    const cards = [...vm.pinCards, ...vm.primaryCards, ...vm.secondaryCards, ...vm.deferredCards];
    const visible = dto.layout_directives.filter((d) => d.slot !== "hidden");
    expect(cards).toHaveLength(visible.length);

    const byId = new Map(cards.map((c) => [c.objectId, c]));
    for (const d of visible) {
      const card = byId.get(d.object_id);
      expect(card).toBeDefined();
      expect(card!.priority).toBe(d.priority);
      expect(card!.slot).toBe(d.slot);
      expect(card!.size).toBe(d.size);
      expect(card!.pinned).toBe(d.pinned);
      expect([...card!.flags]).toEqual([...d.flags]);
    }
  });

  it("hidden directives are excluded from ViewModel bands (not lost from DTO)", () => {
    const hiddenIds = dto.layout_directives
      .filter((d) => d.slot === "hidden")
      .map((d) => d.object_id);
    expect(hiddenIds.length).toBeGreaterThan(0);
    const rendered = new Set(
      [...vm.pinCards, ...vm.primaryCards, ...vm.secondaryCards, ...vm.deferredCards].map(
        (c) => c.objectId,
      ),
    );
    for (const id of hiddenIds) {
      expect(rendered.has(id)).toBe(false);
      expect(dto.layout_directives.some((d) => d.object_id === id)).toBe(true);
    }
  });
});
