import { describe, expect, it } from "vitest";
import { mapWorkspaceError } from "../presentation/mappers/mapWorkspaceError";

describe("mapWorkspaceError", () => {
  it("maps contract codes to presentation surfaces and UI states", () => {
    expect(mapWorkspaceError("WORKSPACE_ACCESS_DENIED", 403)).toMatchObject({
      error: { presentation: "blocking_access_denied", httpStatus: 403 },
      uiState: "Forbidden",
    });
    expect(mapWorkspaceError("WORKSPACE_SESSION_NOT_FOUND", 404)).toMatchObject({
      uiState: "NotFound",
    });
    expect(mapWorkspaceError("WORKSPACE_LENS_UNKNOWN", 422)).toMatchObject({
      error: { presentation: "inline_validation" },
      uiState: null,
    });
    expect(mapWorkspaceError("WORKSPACE_ROLE_UNKNOWN", 422)).toMatchObject({
      error: { presentation: "inline_validation" },
    });
    expect(mapWorkspaceError("WORKSPACE_OBJECT_UNKNOWN", 422)).toMatchObject({
      error: { presentation: "inline_validation" },
    });
    expect(mapWorkspaceError("WORKSPACE_PLAN_STALE", 409)).toMatchObject({
      error: { presentation: "soft_conflict_refetch" },
      shouldRefetch: true,
    });
    expect(mapWorkspaceError("WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE", 409)).toMatchObject({
      error: { presentation: "queue_item_error_refetch" },
      shouldRefetch: true,
    });
    expect(mapWorkspaceError("WORKSPACE_OBJECT_NOT_RESOLVABLE", 409)).toMatchObject({
      error: { presentation: "queue_item_error_refetch" },
      shouldRefetch: true,
    });
    expect(mapWorkspaceError("WORKSPACE_OBJECT_NOT_DISMISSIBLE", 409)).toMatchObject({
      error: { presentation: "queue_item_error_refetch" },
      shouldRefetch: true,
    });
    expect(mapWorkspaceError("WORKSPACE_READ_ONLY", 409)).toMatchObject({
      error: { presentation: "switch_read_only" },
      uiState: "ReadOnly",
    });
    expect(mapWorkspaceError("WORKSPACE_TRACE_DISABLED", 404)).toMatchObject({
      error: { presentation: "hide_trace_panel" },
    });
    expect(mapWorkspaceError("WORKSPACE_COMPUTE_FAILED", 500)).toMatchObject({
      error: { presentation: "retryable_error" },
      uiState: "Error",
    });
  });

  it("maps network failure to retryable error state", () => {
    expect(mapWorkspaceError(null, 0)).toMatchObject({
      error: { presentation: "network_retry" },
      uiState: "Error",
    });
  });
});
