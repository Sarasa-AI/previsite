import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ClinicalContentResponse } from "../../../api/types";
import { WorkspaceApiError } from "../../../api/client";
import { makePlan } from "../../../tests/fixtures";
import { useWorkspaceScreen } from "../useWorkspaceScreen";

const fetchPlan = vi.fn();
const fetchClinicalContent = vi.fn();

vi.mock("../../../application/workspaceService", () => ({
  workspaceService: {
    fetchPlan: (...args: unknown[]) => fetchPlan(...args),
    fetchClinicalContent: (...args: unknown[]) => fetchClinicalContent(...args),
    acknowledge: vi.fn(),
    refreshStory: vi.fn(),
    resolve: vi.fn(),
    dismiss: vi.fn(),
    fetchStoryStatus: vi.fn(),
  },
}));

function contentResponse(contextHash = "abc"): ClinicalContentResponse {
  return {
    session_id: 42,
    context_hash: contextHash,
    content_version: "1.0.0",
    generated_at: "2026-08-01T12:00:00Z",
    content: {
      patient_header: null,
      chief_complaint: { title: "Contract complaint", duration: "", priority: "" },
      hpi: null,
      red_flags: null,
      snapshot: null,
      timeline: null,
      medications: null,
      labs: null,
      missing_info: null,
      soap: null,
      documents: null,
    },
  };
}

function wrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useWorkspaceScreen integration orchestration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchPlan.mockResolvedValue({ notModified: false, plan: makePlan(), etag: "etag-v1", contractVersion: "1.0.0" });
    fetchClinicalContent.mockResolvedValue(contentResponse());
  });

  it("exposes mapped content only after plan and content contexts agree", async () => {
    const { result } = renderHook(() => useWorkspaceScreen({ sessionId: 42, pollIntervalMs: 0 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.consistencyState).toBe("consistent"));
    expect(result.current.viewModel?.metadata.contextHash).toBe("abc");
    expect(result.current.clinicalContent?.chiefComplaint?.title).toBe("Contract complaint");
    expect(result.current.uiState).toBe("Ready");
  });

  it("blocks mismatched plan and clinical content instead of displaying either snapshot", async () => {
    fetchClinicalContent.mockResolvedValue(contentResponse("different-context"));
    const { result } = renderHook(() => useWorkspaceScreen({ sessionId: 42, pollIntervalMs: 0 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.consistencyState).toBe("mismatch"));
    expect(result.current.uiState).toBe("Error");
    expect(result.current.viewModel).toBeNull();
    expect(result.current.clinicalContent).toBeNull();
    expect(result.current.error?.code).toBe("WORKSPACE_CONTEXT_MISMATCH");
  });

  it("does not convert clinical-content transport failure into empty clinical cards", async () => {
    fetchClinicalContent.mockRejectedValue(new WorkspaceApiError("server", 503, "CLINICAL_CONTENT_FAILED"));
    const { result } = renderHook(() => useWorkspaceScreen({ sessionId: 42, pollIntervalMs: 0 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.consistencyState).toBe("content-error"));
    expect(result.current.uiState).toBe("Error");
    expect(result.current.viewModel).toBeNull();
    expect(result.current.clinicalContent).toBeNull();
    expect(result.current.error).toMatchObject({ httpStatus: 503, presentation: "retryable_error" });
  });

  it("maps clinical-content authentication failure to the forbidden state", async () => {
    fetchClinicalContent.mockRejectedValue(new WorkspaceApiError("auth", 401, null));
    const { result } = renderHook(() => useWorkspaceScreen({ sessionId: 42, pollIntervalMs: 0 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.consistencyState).toBe("content-error"));
    expect(result.current.uiState).toBe("Forbidden");
    expect(result.current.error?.httpStatus).toBe(401);
  });

  it("retries both plan and clinical-content requests", async () => {
    fetchClinicalContent.mockRejectedValueOnce(new WorkspaceApiError("network", 0, null)).mockResolvedValueOnce(contentResponse());
    const { result } = renderHook(() => useWorkspaceScreen({ sessionId: 42, pollIntervalMs: 0 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.consistencyState).toBe("content-error"));
    await act(async () => result.current.retry());
    await waitFor(() => expect(result.current.consistencyState).toBe("consistent"));
    expect(fetchPlan.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(fetchClinicalContent).toHaveBeenCalledTimes(2);
  });
});
