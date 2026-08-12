import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { WorkspaceApiError } from "../../../api/client";
import { makePlan } from "../../../tests/fixtures";
import { useWorkspacePlan } from "../useWorkspacePlan";

const fetchPlan = vi.fn();
const acknowledge = vi.fn();
const refreshStory = vi.fn();
const resolve = vi.fn();
const dismiss = vi.fn();
const fetchStoryStatus = vi.fn();

vi.mock("../../../application/workspaceService", () => ({
  workspaceService: {
    fetchPlan: (...args: unknown[]) => fetchPlan(...args),
    acknowledge: (...args: unknown[]) => acknowledge(...args),
    refreshStory: (...args: unknown[]) => refreshStory(...args),
    resolve: (...args: unknown[]) => resolve(...args),
    dismiss: (...args: unknown[]) => dismiss(...args),
    fetchStoryStatus: (...args: unknown[]) => fetchStoryStatus(...args),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { Wrapper, queryClient };
}

describe("useWorkspacePlan mutations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const plan = makePlan({ plan_etag: "etag-v1", workspace_state: "review_needed" });
    fetchPlan.mockResolvedValue({
      plan,
      etag: "etag-v1",
      contractVersion: "1.0.0",
      notModified: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolve full-replaces plan and updates etag (no merge)", async () => {
    const after = makePlan({
      plan_etag: "etag-v2",
      workspace_state: "verified",
      decision_queue: [],
    });
    resolve.mockResolvedValue({
      plan: after,
      etag: "etag-v2",
      contractVersion: "1.0.0",
    });

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useWorkspacePlan({ sessionId: 42, pollIntervalMs: 0 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.viewModel).not.toBeNull());
    expect(result.current.etag).toBe("etag-v1");

    await act(async () => {
      result.current.resolve("critical_alerts");
    });

    await waitFor(() => expect(result.current.etag).toBe("etag-v2"));
    expect(resolve).toHaveBeenCalledWith(42, "critical_alerts", "etag-v1");
    expect(result.current.viewModel?.workspaceState).toBe("verified");
    expect(result.current.viewModel?.queue).toHaveLength(0);
    expect(result.current.viewModel?.planEtag).toBe("etag-v2");
  });

  it("dismiss full-replaces plan and updates etag", async () => {
    const after = makePlan({
      plan_etag: "etag-dismissed",
      workspace_state: "review_needed",
      decision_queue: [],
    });
    dismiss.mockResolvedValue({
      plan: after,
      etag: "etag-dismissed",
      contractVersion: "1.0.0",
    });

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useWorkspacePlan({ sessionId: 42, pollIntervalMs: 0 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.viewModel).not.toBeNull());

    await act(async () => {
      result.current.dismiss("critical_alerts");
    });

    await waitFor(() => expect(result.current.etag).toBe("etag-dismissed"));
    expect(dismiss).toHaveBeenCalledWith(42, "critical_alerts", "etag-v1");
    expect(result.current.viewModel?.planEtag).toBe("etag-dismissed");
  });

  it("WORKSPACE_PLAN_STALE on resolve triggers refetch + full-replace", async () => {
    resolve.mockRejectedValue(
      new WorkspaceApiError("stale", 409, "WORKSPACE_PLAN_STALE"),
    );
    const fresh = makePlan({
      plan_etag: "etag-fresh",
      workspace_state: "verified",
      decision_queue: [],
    });
    fetchPlan
      .mockResolvedValueOnce({
        plan: makePlan({ plan_etag: "etag-v1", workspace_state: "review_needed" }),
        etag: "etag-v1",
        contractVersion: "1.0.0",
        notModified: false,
      })
      .mockResolvedValueOnce({
        plan: fresh,
        etag: "etag-fresh",
        contractVersion: "1.0.0",
        notModified: false,
      });

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useWorkspacePlan({ sessionId: 42, pollIntervalMs: 0 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.etag).toBe("etag-v1"));

    await act(async () => {
      result.current.resolve("critical_alerts");
    });

    // Soft conflict: invalidate → GET full-replaces snapshot (error may clear after refetch).
    await waitFor(() => expect(result.current.etag).toBe("etag-fresh"));
    expect(fetchPlan.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(result.current.viewModel?.planEtag).toBe("etag-fresh");
    expect(result.current.viewModel?.queue).toHaveLength(0);
    expect(result.current.viewModel?.workspaceState).toBe("verified");
  });

  it("story-status poll invalidates plan query on ready", async () => {
    const refreshed = makePlan({
      plan_etag: "etag-after-refresh",
      story: { text: "fresh story", confidence: 1, evidence_refs: [], stale: false },
    });
    refreshStory.mockResolvedValue({
      plan: makePlan({ plan_etag: "etag-refreshing", story: { text: "x", confidence: 1, evidence_refs: [], stale: true } }),
      etag: "etag-refreshing",
      contractVersion: "1.0.0",
    });
    fetchStoryStatus.mockResolvedValue({
      story_status: "ready",
      context_hash: "abc",
      stale: false,
      plan_etag: "etag-after-refresh",
    });
    fetchPlan
      .mockResolvedValueOnce({
        plan: makePlan({ plan_etag: "etag-v1" }),
        etag: "etag-v1",
        contractVersion: "1.0.0",
        notModified: false,
      })
      .mockResolvedValueOnce({
        plan: refreshed,
        etag: "etag-after-refresh",
        contractVersion: "1.0.0",
        notModified: false,
      });

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useWorkspacePlan({ sessionId: 42, pollIntervalMs: 0 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.viewModel).not.toBeNull());

    await act(async () => {
      result.current.refreshStory();
    });

    await waitFor(() => expect(fetchStoryStatus).toHaveBeenCalled());
    await waitFor(() => expect(result.current.etag).toBe("etag-after-refresh"));
    expect(result.current.viewModel?.story?.text).toBe("fresh story");
  });

  it("does not mutate when mutationsAllowed is false", async () => {
    fetchPlan.mockResolvedValue({
      plan: makePlan({ plan_etag: "etag-ro", workspace_state: "read_only" }),
      etag: "etag-ro",
      contractVersion: "1.0.0",
      notModified: false,
    });

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useWorkspacePlan({ sessionId: 42, pollIntervalMs: 0 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.viewModel?.mutationsAllowed).toBe(false));

    await act(async () => {
      result.current.resolve("critical_alerts");
      result.current.dismiss("critical_alerts");
    });

    expect(resolve).not.toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
  });
});
