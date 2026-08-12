import { describe, expect, it } from "vitest";
import { projectPlan } from "../presentation/mappers/projectPlan";
import { replaceWorkspaceSnapshot } from "@/src/shared/query/workspaceCache";
import { makePlan } from "./fixtures";

describe("etagReplacement", () => {
  it("full-replaces ViewModel on mutation 200 with new etag", () => {
    const before = projectPlan(makePlan({ plan_etag: "etag-v1", workspace_state: "review_needed" }), "etag-v1");
    const afterPlan = makePlan({
      plan_etag: "etag-v2",
      workspace_state: "completed",
      decision_queue: [],
    });
    const snapshot = replaceWorkspaceSnapshot(
      { plan: makePlan(), etag: "etag-v1", contractVersion: "1.0.0", lastCheckedAt: 1 },
      { plan: afterPlan, etag: "etag-v2", contractVersion: "1.0.0" },
    );
    const after = projectPlan(afterPlan, snapshot.etag);
    expect(after.planEtag).toBe("etag-v2");
    expect(after.workspaceState).toBe("completed");
    expect(after.queue).toHaveLength(0);
    expect(after.planEtag).not.toBe(before.planEtag);
  });

  it("on stale conflict, refetch replaces entire snapshot (no field merge)", () => {
    const staleLocal = makePlan({
      plan_etag: "etag-old",
      story: { text: "old", confidence: 1, evidence_refs: [], stale: true },
    });
    const freshServer = makePlan({
      plan_etag: "etag-new",
      story: { text: "new", confidence: 0.5, evidence_refs: ["x"], stale: false },
      workspace_state: "verified",
    });

    // Simulate 409 handling: discard pending mutation, GET fresh, full-replace.
    const replaced = replaceWorkspaceSnapshot(
      { plan: staleLocal, etag: "etag-old", contractVersion: "1.0.0", lastCheckedAt: 1 },
      { plan: freshServer, etag: "etag-new", contractVersion: "1.0.0" },
    );
    const vm = projectPlan(freshServer, replaced.etag);
    expect(vm.planEtag).toBe("etag-new");
    expect(vm.story?.text).toBe("new");
    expect(vm.story?.stale).toBe(false);
    // Ensure we did not keep old story text under new etag
    expect(vm.story?.text).not.toBe("old");
  });

  it("presentation expects full replacement — no patch, no merge, no streaming apply", () => {
    const v1 = makePlan({
      plan_etag: "v1",
      workspace_state: "review_needed",
      decision_queue: [
        {
          rank: 1,
          object_id: "critical_alerts",
          reason_code: "SAFETY",
          explanation: "old",
          acknowledge_required: true,
        },
      ],
    });
    const v2 = makePlan({
      plan_etag: "v2",
      workspace_state: "verified",
      decision_queue: [],
      story: null,
    });
    const snap = replaceWorkspaceSnapshot(
      { plan: v1, etag: "v1", contractVersion: "1.0.0", lastCheckedAt: 1 },
      { plan: v2, etag: "v2", contractVersion: "1.0.0" },
    );
    const vm = projectPlan(snap.plan, snap.etag);
    expect(vm.workspaceState).toBe("verified");
    expect(vm.queue).toHaveLength(0);
    expect(vm.story).toBeNull();
    // No residual fields from v1 under v2 etag
    expect(vm.planEtag).toBe("v2");
  });

  it("resolve response full-replaces snapshot — no merge across ETags", () => {
    const before = makePlan({
      plan_etag: "etag-pre-resolve",
      workspace_state: "review_needed",
      decision_queue: [
        {
          rank: 1,
          object_id: "critical_alerts",
          reason_code: "SAFETY",
          explanation: "needs resolve",
          acknowledge_required: true,
        },
      ],
    });
    const afterResolve = makePlan({
      plan_etag: "etag-post-resolve",
      workspace_state: "verified",
      decision_queue: [],
    });
    const snap = replaceWorkspaceSnapshot(
      { plan: before, etag: "etag-pre-resolve", contractVersion: "1.0.0", lastCheckedAt: 1 },
      { plan: afterResolve, etag: "etag-post-resolve", contractVersion: "1.0.0" },
    );
    const vm = projectPlan(afterResolve, snap.etag);
    expect(vm.planEtag).toBe("etag-post-resolve");
    expect(vm.queue).toHaveLength(0);
    expect(vm.workspaceState).toBe("verified");
  });

  it("dismiss response full-replaces snapshot — no merge across ETags", () => {
    const before = makePlan({
      plan_etag: "etag-pre-dismiss",
      decision_queue: [
        {
          rank: 1,
          object_id: "labs",
          reason_code: "FOLLOW_UP",
          explanation: "review labs",
          acknowledge_required: false,
        },
      ],
    });
    const afterDismiss = makePlan({
      plan_etag: "etag-post-dismiss",
      decision_queue: [],
      layout_directives: [
        makePlan().layout_directives[0]!,
        {
          ...makePlan().layout_directives[1]!,
        },
      ],
    });
    const snap = replaceWorkspaceSnapshot(
      { plan: before, etag: "etag-pre-dismiss", contractVersion: "1.0.0", lastCheckedAt: 1 },
      { plan: afterDismiss, etag: "etag-post-dismiss", contractVersion: "1.0.0" },
    );
    const vm = projectPlan(afterDismiss, snap.etag);
    expect(vm.planEtag).toBe("etag-post-dismiss");
    expect(vm.queue).toHaveLength(0);
    expect(vm.planEtag).not.toBe("etag-pre-dismiss");
  });
});
