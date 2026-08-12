import { describe, expect, it, vi, beforeEach } from "vitest";
import { projectPlan } from "../presentation/mappers/projectPlan";
import { onWorkspaceTelemetry } from "@/src/shared/utils/telemetry";
import { makeDirective, makePlan, makeTrust } from "./fixtures";

describe("projectPlan", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("projects bands and skips hidden directives", () => {
    const vm = projectPlan(makePlan(), "etag-v1");
    expect(vm.pinCards.map((c) => c.objectId)).toEqual(["critical_alerts"]);
    expect(vm.primaryCards.map((c) => c.objectId)).toEqual(["chief_complaint"]);
    expect(vm.secondaryCards.map((c) => c.objectId)).toEqual(["pmh"]);
    expect(vm.deferredCards.map((c) => c.objectId)).toEqual(["documents"]);
    expect(vm.pinCards.concat(vm.primaryCards, vm.secondaryCards, vm.deferredCards).some((c) => c.objectId === "labs")).toBe(
      false,
    );
  });

  it("orders pin band by pin_zone first", () => {
    const plan = makePlan({
      pin_zone: ["allergies", "critical_alerts"],
      layout_directives: [
        makeDirective({ object_id: "critical_alerts", slot: "pin", priority: "p0", pinned: true }),
        makeDirective({ object_id: "allergies", slot: "pin", priority: "p0", pinned: true }),
        makeDirective({ object_id: "red_flags", slot: "pin", priority: "p0", pinned: true }),
      ],
    });
    const vm = projectPlan(plan, "etag-v1");
    expect(vm.pinCards.map((c) => c.objectId)).toEqual([
      "allergies",
      "critical_alerts",
      "red_flags",
    ]);
  });

  it("maps confidence null to unknown, never 0", () => {
    const plan = makePlan({
      story: {
        text: "Story",
        confidence: null,
        evidence_refs: [],
        stale: false,
      },
      layout_directives: [
        makeDirective({
          object_id: "chief_complaint",
          slot: "primary",
          trust: makeTrust({ confidence: null }),
        }),
      ],
    });
    const vm = projectPlan(plan, "etag-v1");
    expect(vm.story?.confidence).toBe("unknown");
    expect(vm.primaryCards[0]?.trust.confidence).toBe("unknown");
  });

  it("sets mutationsAllowed false for loading/read_only/offline", () => {
    expect(projectPlan(makePlan({ workspace_state: "loading" }), "e").mutationsAllowed).toBe(false);
    expect(projectPlan(makePlan({ workspace_state: "read_only" }), "e").mutationsAllowed).toBe(false);
    expect(projectPlan(makePlan({ workspace_state: "offline" }), "e").mutationsAllowed).toBe(false);
    expect(projectPlan(makePlan({ workspace_state: "verified" }), "e").mutationsAllowed).toBe(true);
  });

  it("skips unknown object_id with telemetry and does not throw", () => {
    const events: string[] = [];
    const stop = onWorkspaceTelemetry((event) => {
      events.push(event);
    });
    const plan = makePlan({
      layout_directives: [
        makeDirective({ object_id: "future_object", slot: "primary" }),
        makeDirective({ object_id: "chief_complaint", slot: "primary" }),
      ],
    });
    const vm = projectPlan(plan, "etag-v1");
    stop();
    expect(vm.primaryCards.map((c) => c.objectId)).toEqual(["chief_complaint"]);
    expect(events).toContain("workspace.unknown_object_id");
  });

  it("uses provided etag and freezes the snapshot shape", () => {
    const vm = projectPlan(makePlan({ plan_etag: "body-etag" }), "header-etag");
    expect(vm.planEtag).toBe("header-etag");
    expect(Object.isFrozen(vm)).toBe(true);
    expect(Object.isFrozen(vm.pinCards)).toBe(true);
  });

  it("deep-freezes nested trust, queue items, story, and band arrays", () => {
    const vm = projectPlan(
      makePlan({
        layout_directives: [
          makeDirective({
            object_id: "chief_complaint",
            slot: "primary",
            trust: makeTrust({ confidence: null, evidence_refs: ["a", "b"] }),
          }),
        ],
        decision_queue: [
          {
            rank: 1,
            object_id: "chief_complaint",
            reason_code: "ORIENT",
            explanation: "Orient",
            acknowledge_required: false,
          },
        ],
        story: {
          text: "Immutable story",
          confidence: null,
          evidence_refs: ["s1"],
          stale: false,
        },
      }),
      "etag-freeze",
    );
    expect(Object.isFrozen(vm.primaryCards)).toBe(true);
    expect(Object.isFrozen(vm.primaryCards[0]!.trust.allProvenance)).toBe(true);
    expect(Object.isFrozen(vm.primaryCards[0]!.trust.evidenceRefs)).toBe(true);
    expect(Object.isFrozen(vm.primaryCards[0]!.flags)).toBe(true);
    expect(Object.isFrozen(vm.queue)).toBe(true);
    expect(Object.isFrozen(vm.queue[0])).toBe(true);
    expect(Object.isFrozen(vm.story)).toBe(true);
    expect(Object.isFrozen(vm.story!.evidenceRefs)).toBe(true);
    expect(vm.primaryCards[0]!.trust.confidence).toBe("unknown");
  });
});
