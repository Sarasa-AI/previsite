"use client";

import { useCallback, useMemo } from "react";
import { WorkspaceApiError } from "../../api/client";
import { mapWorkspaceError } from "../mappers/mapWorkspaceError";
import { useClinicalContent } from "./useClinicalContent";
import { useWorkspacePlan, type UseWorkspacePlanParams } from "./useWorkspacePlan";
import type { ErrorViewModel } from "../viewmodels/types";
import type { WorkspaceUiState } from "../state/workspaceUiState";

export type WorkspaceConsistencyState = "waiting-for-plan" | "loading-content" | "consistent" | "mismatch" | "content-error";

export function useWorkspaceScreen(params: UseWorkspacePlanParams) {
  const workspace = useWorkspacePlan(params);
  const planContextHash = workspace.viewModel?.metadata.contextHash ?? null;
  const content = useClinicalContent({
    sessionId: params.sessionId,
    contextHash: planContextHash,
    enabled: workspace.viewModel != null,
  });

  const consistencyState: WorkspaceConsistencyState = useMemo(() => {
    if (!workspace.viewModel) return "waiting-for-plan";
    if (!content.projection) return content.error ? "content-error" : "loading-content";
    if (
      String(content.projection.sessionId) !== String(params.sessionId) ||
      content.projection.contextHash !== workspace.viewModel.metadata.contextHash
    ) return "mismatch";
    return "consistent";
  }, [content.error, content.projection, params.sessionId, workspace.viewModel]);

  const contentError: ErrorViewModel | null = useMemo(() => {
    if (consistencyState === "mismatch") {
      return { code: "WORKSPACE_CONTEXT_MISMATCH", httpStatus: 409, presentation: "soft_conflict_refetch" };
    }
    if (consistencyState !== "content-error") return null;
    const status = content.error instanceof WorkspaceApiError ? content.error.status : 0;
    const code = content.error instanceof WorkspaceApiError ? content.error.code : null;
    return mapWorkspaceError(code, status).error;
  }, [consistencyState, content.error]);

  const retry = useCallback(() => {
    workspace.retry();
    void content.refetch();
  }, [content, workspace]);

  let uiState: WorkspaceUiState = workspace.uiState;
  let viewModel = workspace.viewModel;
  let clinicalContent = content.clinicalContent;
  let error = workspace.error;

  if (workspace.viewModel && consistencyState === "loading-content") {
    uiState = "Loading";
    viewModel = null;
    clinicalContent = null;
  } else if (workspace.viewModel && (consistencyState === "mismatch" || consistencyState === "content-error")) {
    const mapped = contentError ? mapWorkspaceError(contentError.code, contentError.httpStatus) : null;
    uiState = mapped?.uiState === "Forbidden" || mapped?.uiState === "NotFound" ? mapped.uiState : "Error";
    viewModel = null;
    clinicalContent = null;
    error = contentError;
  }

  return {
    ...workspace,
    uiState,
    viewModel,
    clinicalContent: consistencyState === "consistent" ? clinicalContent : null,
    error,
    retry,
    consistencyState,
    clinicalContentLoading: content.isLoading,
    clinicalContentFetching: content.isFetching,
  };
}
