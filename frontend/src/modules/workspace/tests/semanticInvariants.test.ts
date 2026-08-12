/**
 * Semantic invariants: DTO → projectPlan → WorkspaceViewModel.
 * Complements field-mapping / contractCompleteness tests.
 */

import { describe, expect, it } from "vitest";
import { projectPlan } from "../presentation/mappers/projectPlan";
import {
  GOLDEN_NARRATIVE,
  GOLDEN_OBJECT_IDS,
  GOLDEN_WORKSPACE_PLAN,
} from "./goldenClinicalDataset";
import { makeDirective, makePlan, makeTrust } from "./fixtures";

describe("Semantic invariants: DTO → ViewModel", () => {
  const vm = projectPlan(GOLDEN_WORKSPACE_PLAN, GOLDEN_WORKSPACE_PLAN.plan_etag);

  it("identity: object IDs unchanged, no duplicates, no missing supported IDs in bands", () => {
    const rendered = [
      ...vm.pinCards,
      ...vm.primaryCards,
      ...vm.secondaryCards,
      ...vm.deferredCards,
    ].map((c) => c.objectId);

    expect(new Set(rendered).size).toBe(rendered.length);

    const hidden = GOLDEN_WORKSPACE_PLAN.layout_directives
      .filter((d) => d.slot === "hidden")
      .map((d) => d.object_id);

    for (const id of hidden) {
      expect(rendered).not.toContain(id);
    }

    const expectedVisible = GOLDEN_OBJECT_IDS.filter((id) => !hidden.includes(id));
    expect(new Set(rendered)).toEqual(new Set(expectedVisible));
  });

  it("priority: values never change after mapping", () => {
    const byDto = new Map(
      GOLDEN_WORKSPACE_PLAN.layout_directives.map((d) => [d.object_id, d.priority]),
    );
    for (const card of [
      ...vm.pinCards,
      ...vm.primaryCards,
      ...vm.secondaryCards,
      ...vm.deferredCards,
    ]) {
      expect(card.priority).toBe(byDto.get(card.objectId));
    }
  });

  it("visibility: hidden stay hidden; deferred stay deferred; pinned stay pinned", () => {
    expect(
      [...vm.pinCards, ...vm.primaryCards, ...vm.secondaryCards, ...vm.deferredCards].some(
        (c) =>
          GOLDEN_WORKSPACE_PLAN.layout_directives.find((d) => d.object_id === c.objectId)
            ?.slot === "hidden",
      ),
    ).toBe(false);

    expect(vm.deferredCards.every((c) => c.slot === "deferred")).toBe(true);
    expect(vm.pinCards.every((c) => c.pinned && c.slot === "pin")).toBe(true);

    for (const objectId of GOLDEN_WORKSPACE_PLAN.pin_zone) {
      expect(vm.pinCards.map((c) => c.objectId)).toContain(objectId);
    }
  });

  it("trust: metadata identical (null confidence → unknown); never fabricated", () => {
    const byDto = new Map(
      GOLDEN_WORKSPACE_PLAN.layout_directives.map((d) => [d.object_id, d.trust]),
    );
    for (const card of [
      ...vm.pinCards,
      ...vm.primaryCards,
      ...vm.secondaryCards,
      ...vm.deferredCards,
    ]) {
      const trust = byDto.get(card.objectId)!;
      expect(card.trust.primaryProvenance).toBe(trust.primary_provenance);
      expect([...card.trust.allProvenance]).toEqual([...trust.all_provenance]);
      expect(card.trust.verification).toBe(trust.verification);
      expect([...card.trust.evidenceRefs]).toEqual([...trust.evidence_refs]);
      if (trust.confidence === null) {
        expect(card.trust.confidence).toBe("unknown");
      } else {
        expect(card.trust.confidence).toBe(trust.confidence);
      }
    }
  });

  it("ordering: pin_zone order and band order preserved", () => {
    expect(vm.pinCards.map((c) => c.objectId)).toEqual([
      ...GOLDEN_WORKSPACE_PLAN.pin_zone,
    ]);

    const primaryDto = GOLDEN_WORKSPACE_PLAN.layout_directives
      .filter((d) => d.slot === "primary")
      .map((d) => d.object_id);
    expect(vm.primaryCards.map((c) => c.objectId)).toEqual(primaryDto);

    const secondaryDto = GOLDEN_WORKSPACE_PLAN.layout_directives
      .filter((d) => d.slot === "secondary")
      .map((d) => d.object_id);
    expect(vm.secondaryCards.map((c) => c.objectId)).toEqual(secondaryDto);

    const deferredDto = GOLDEN_WORKSPACE_PLAN.layout_directives
      .filter((d) => d.slot === "deferred")
      .map((d) => d.object_id);
    expect(vm.deferredCards.map((c) => c.objectId)).toEqual(deferredDto);

    expect(vm.queue.map((q) => q.rank)).toEqual(
      GOLDEN_WORKSPACE_PLAN.decision_queue.map((q) => q.rank),
    );
    expect(vm.queue.map((q) => q.objectId)).toEqual(
      GOLDEN_WORKSPACE_PLAN.decision_queue.map((q) => q.object_id),
    );
  });

  it("narrative: story text is not truncated, reordered, or modified", () => {
    expect(vm.story).not.toBeNull();
    expect(vm.story!.text).toBe(GOLDEN_NARRATIVE.storyText);
    expect(vm.story!.text).toBe(GOLDEN_WORKSPACE_PLAN.story!.text);
    expect(vm.story!.stale).toBe(false);
  });

  it("deep freezes nested trust and queue (immutable ViewModel)", () => {
    expect(Object.isFrozen(vm)).toBe(true);
    expect(Object.isFrozen(vm.pinCards)).toBe(true);
    expect(Object.isFrozen(vm.primaryCards)).toBe(true);
    expect(Object.isFrozen(vm.queue)).toBe(true);
    expect(Object.isFrozen(vm.queue[0])).toBe(true);
    expect(Object.isFrozen(vm.pinCards[0]!.trust.allProvenance)).toBe(true);
    expect(Object.isFrozen(vm.pinCards[0]!.trust.evidenceRefs)).toBe(true);
    if (vm.story) {
      expect(Object.isFrozen(vm.story)).toBe(true);
      expect(Object.isFrozen(vm.story.evidenceRefs)).toBe(true);
    }
  });
});

describe("Semantic invariants: edge visibility", () => {
  it("preserves visibility_reason semantics for hidden cards on the DTO only", () => {
    const plan = makePlan({
      layout_directives: [
        makeDirective({
          object_id: "labs",
          slot: "hidden",
          priority: "p3",
          visibility_reason: "cognitive_budget",
          trust: makeTrust({ confidence: null }),
        }),
        makeDirective({ object_id: "chief_complaint", slot: "primary", priority: "p0" }),
      ],
    });
    const vm = projectPlan(plan, "e");
    expect(vm.primaryCards.map((c) => c.objectId)).toEqual(["chief_complaint"]);
    expect(
      [...vm.pinCards, ...vm.primaryCards, ...vm.secondaryCards, ...vm.deferredCards].some(
        (c) => c.objectId === "labs",
      ),
    ).toBe(false);
  });
});
