import { describe, expect, it } from "vitest";
import {
  assertSameEtagOrReplace,
  keepWorkspaceSnapshotOn304,
  replaceWorkspaceSnapshot,
  workspaceQueryKey,
  type WorkspaceServerSnapshot,
} from "@/src/shared/query/workspaceCache";
import { makePlan } from "./fixtures";

describe("workspaceCache", () => {
  it("keys cache by session_id, lens, role", () => {
    expect(workspaceQueryKey({ sessionId: 42, lens: "cardiology", role: "resident" })).toEqual([
      "workspace",
      "42",
      "cardiology",
      "resident",
    ]);
    expect(workspaceQueryKey({ sessionId: 1, lens: "a", role: "b" })).not.toEqual(
      workspaceQueryKey({ sessionId: 1, lens: "a", role: "c" }),
    );
  });

  it("keeps plan on 304 and only updates lastCheckedAt", () => {
    const previous: WorkspaceServerSnapshot = {
      plan: makePlan({ plan_etag: "etag-v1" }),
      etag: "etag-v1",
      contractVersion: "1.0.0",
      lastCheckedAt: 1000,
    };
    const kept = keepWorkspaceSnapshotOn304(previous);
    expect(kept.plan).toBe(previous.plan);
    expect(kept.etag).toBe("etag-v1");
    expect(kept.lastCheckedAt).toBeGreaterThanOrEqual(1000);
  });

  it("atomically replaces on 200 and never merges across etags", () => {
    const previous: WorkspaceServerSnapshot = {
      plan: makePlan({ plan_etag: "etag-v1", workspace_state: "loading" }),
      etag: "etag-v1",
      contractVersion: "1.0.0",
      lastCheckedAt: 1000,
    };
    const nextPlan = makePlan({ plan_etag: "etag-v2", workspace_state: "verified" });
    const replaced = replaceWorkspaceSnapshot(previous, {
      plan: nextPlan,
      etag: "etag-v2",
      contractVersion: "1.0.0",
    });
    expect(replaced.etag).toBe("etag-v2");
    expect(replaced.plan).toBe(nextPlan);
    expect((replaced.plan as ReturnType<typeof makePlan>).workspace_state).toBe("verified");
    expect(assertSameEtagOrReplace("etag-v1", "etag-v2")).toBe("replace");
    expect(assertSameEtagOrReplace("etag-v2", "etag-v2")).toBe("keep");
  });
});
