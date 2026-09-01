import { afterEach, describe, expect, it, vi } from "vitest";
import { acknowledgeWorkspaceObject, getClinicalContent, getWorkspace } from "./client";
import { makePlan } from "../tests/fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("workspace API client contract headers", () => {
  it("sends If-None-Match and preserves the cached etag on 304", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 304 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getWorkspace(42, { lens: "general_medicine", role: "doctor" }, { ifNoneMatch: "etag-v1" });
    const [, init] = fetchMock.mock.calls[0]!;
    expect((init.headers as Headers).get("If-None-Match")).toBe("etag-v1");
    expect(result).toMatchObject({ notModified: true, etag: "etag-v1" });
  });

  it("sends If-Match on mutations and returns the replacement snapshot etag", async () => {
    const plan = makePlan({ plan_etag: "etag-v2" });
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(plan), {
      status: 200,
      headers: { "Content-Type": "application/json", ETag: '"etag-v2"', "X-Workspace-Contract-Version": "1.0.0" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await acknowledgeWorkspaceObject(42, { object_id: "critical_alerts" }, "etag-v1");
    const [, init] = fetchMock.mock.calls[0]!;
    expect((init.headers as Headers).get("If-Match")).toBe("etag-v1");
    expect(result.etag).toBe("etag-v2");
    expect(result.plan).toEqual(plan);
  });

  it("fetches clinical content only from the contract endpoint with credentials", async () => {
    const response = { session_id: 42, context_hash: "abc", content_version: "1.0.0", generated_at: "", content: {} };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await getClinicalContent(42);
    expect(fetchMock).toHaveBeenCalledWith("/api/proxy/api/sessions/42/clinical-content", expect.objectContaining({ method: "GET", credentials: "include" }));
  });
});
