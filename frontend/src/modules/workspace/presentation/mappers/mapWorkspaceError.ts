/**
 * Map API contract error codes to presentation ErrorViewModel / UI states.
 * Never invent frontend-only error semantics.
 */

import type { ErrorPresentation, ErrorViewModel } from "../viewmodels/types";
import type { WorkspaceUiState } from "../state/workspaceUiState";

export type MappedWorkspaceError = {
  error: ErrorViewModel;
  uiState: WorkspaceUiState | null;
  /** Soft conflicts require refetch + full-replace. */
  shouldRefetch: boolean;
};

const CODE_MAP: Record<
  string,
  { presentation: ErrorPresentation; uiState: WorkspaceUiState | null; shouldRefetch: boolean }
> = {
  WORKSPACE_ACCESS_DENIED: {
    presentation: "blocking_access_denied",
    uiState: "Forbidden",
    shouldRefetch: false,
  },
  WORKSPACE_SESSION_NOT_FOUND: {
    presentation: "blocking_access_denied",
    uiState: "NotFound",
    shouldRefetch: false,
  },
  WORKSPACE_LENS_UNKNOWN: {
    presentation: "inline_validation",
    uiState: null,
    shouldRefetch: false,
  },
  WORKSPACE_ROLE_UNKNOWN: {
    presentation: "inline_validation",
    uiState: null,
    shouldRefetch: false,
  },
  WORKSPACE_OBJECT_UNKNOWN: {
    presentation: "inline_validation",
    uiState: null,
    shouldRefetch: false,
  },
  WORKSPACE_PLAN_STALE: {
    presentation: "soft_conflict_refetch",
    uiState: null,
    shouldRefetch: true,
  },
  WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE: {
    presentation: "queue_item_error_refetch",
    uiState: null,
    shouldRefetch: true,
  },
  WORKSPACE_OBJECT_NOT_RESOLVABLE: {
    presentation: "queue_item_error_refetch",
    uiState: null,
    shouldRefetch: true,
  },
  WORKSPACE_OBJECT_NOT_DISMISSIBLE: {
    presentation: "queue_item_error_refetch",
    uiState: null,
    shouldRefetch: true,
  },
  WORKSPACE_READ_ONLY: {
    presentation: "switch_read_only",
    uiState: "ReadOnly",
    shouldRefetch: false,
  },
  WORKSPACE_TRACE_DISABLED: {
    presentation: "hide_trace_panel",
    uiState: null,
    shouldRefetch: false,
  },
  WORKSPACE_COMPUTE_FAILED: {
    presentation: "retryable_error",
    uiState: "Error",
    shouldRefetch: false,
  },
};

export function mapWorkspaceError(
  code: string | null | undefined,
  httpStatus: number,
): MappedWorkspaceError {
  if (code && CODE_MAP[code]) {
    const mapped = CODE_MAP[code];
    return {
      error: {
        code,
        httpStatus,
        presentation: mapped.presentation,
      },
      uiState: mapped.uiState,
      shouldRefetch: mapped.shouldRefetch,
    };
  }

  if (httpStatus === 403) {
    return {
      error: {
        code: code ?? "WORKSPACE_ACCESS_DENIED",
        httpStatus,
        presentation: "blocking_access_denied",
      },
      uiState: "Forbidden",
      shouldRefetch: false,
    };
  }

  if (httpStatus === 404) {
    return {
      error: {
        code: code ?? "WORKSPACE_SESSION_NOT_FOUND",
        httpStatus,
        presentation: "blocking_access_denied",
      },
      uiState: "NotFound",
      shouldRefetch: false,
    };
  }

  if (httpStatus >= 500 || httpStatus === 0) {
    return {
      error: {
        code: code ?? "NETWORK_OR_SERVER",
        httpStatus,
        presentation: httpStatus === 0 ? "network_retry" : "retryable_error",
      },
      uiState: "Error",
      shouldRefetch: false,
    };
  }

  return {
    error: {
      code: code ?? "UNKNOWN",
      httpStatus,
      presentation: "unknown",
    },
    uiState: "Error",
    shouldRefetch: false,
  };
}
