"use client";

/**
 * Server-state hook for WorkspacePlan.
 * React Query owns plan/etag/loading/refresh/cache only.
 * Presentation UI state (expanded cards, focus, etc.) stays outside.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkspaceApiError } from "../../api/client";
import type { WorkspacePlanResponse } from "../../api/types";
import { workspaceService } from "../../application/workspaceService";
import { mapWorkspaceError } from "../mappers/mapWorkspaceError";
import { projectPlan } from "../mappers/projectPlan";
import {
  deriveWorkspaceUiState,
  type WorkspaceUiState,
} from "../state/workspaceUiState";
import type { ErrorViewModel, WorkspaceViewModel } from "../viewmodels/types";
import {
  keepWorkspaceSnapshotOn304,
  replaceWorkspaceSnapshot,
  workspaceBackoffDelay,
  workspaceQueryKey,
  WORKSPACE_RETRY,
  type WorkspaceServerSnapshot,
} from "@/src/shared/query/workspaceCache";
import { emitWorkspaceTelemetry } from "@/src/shared/utils/telemetry";
import { WORKSPACE_CONTRACT_VERSION } from "../../api/types";

export type UseWorkspacePlanParams = {
  sessionId: number | string;
  lens?: string;
  role?: string;
  offline?: boolean;
  /** Poll interval while session open (ms). 0 disables. */
  pollIntervalMs?: number;
};

type CachedPlan = WorkspaceServerSnapshot & {
  plan: WorkspacePlanResponse;
};

function majorVersion(version: string): string {
  return version.split(".")[0] ?? version;
}

const STORY_STATUS_POLL_MS = 2_000;

export function useWorkspacePlan({
  sessionId,
  lens = "general_medicine",
  role = "doctor",
  offline = false,
  pollIntervalMs = 15_000,
}: UseWorkspacePlanParams) {
  const queryClient = useQueryClient();
  const queryKey = workspaceQueryKey({ sessionId, lens, role });
  const etagRef = useRef<string | null>(null);
  const [clientOffline, setClientOffline] = useState(false);
  const [errorView, setErrorView] = useState<ErrorViewModel | null>(null);
  const [errorUiState, setErrorUiState] = useState<
    Extract<WorkspaceUiState, "Forbidden" | "NotFound" | "Error"> | null
  >(null);
  const [pollStoryStatus, setPollStoryStatus] = useState(false);

  useEffect(() => {
    const onOnline = () => setClientOffline(false);
    const onOffline = () => setClientOffline(true);
    if (typeof window !== "undefined") {
      setClientOffline(!navigator.onLine);
      window.addEventListener("online", onOnline);
      window.addEventListener("offline", onOffline);
      return () => {
        window.removeEventListener("online", onOnline);
        window.removeEventListener("offline", onOffline);
      };
    }
  }, []);

  const query = useQuery({
    queryKey,
    queryFn: async ({ signal }): Promise<CachedPlan | null> => {
      const previous = queryClient.getQueryData<CachedPlan>(queryKey);
      const ifNoneMatch = previous?.etag ?? etagRef.current ?? undefined;

      try {
        const result = await workspaceService.fetchPlan(
          sessionId,
          { lens, role, offline: offline || clientOffline },
          { ifNoneMatch: ifNoneMatch ?? undefined, signal },
        );

        if (result.notModified) {
          if (previous) {
            const kept = keepWorkspaceSnapshotOn304(previous) as CachedPlan;
            etagRef.current = kept.etag;
            setErrorView(null);
            setErrorUiState(null);
            return kept;
          }
          // 304 without prior plan should not happen; fall through as empty.
          return previous ?? null;
        }

        const major = majorVersion(result.contractVersion);
        if (major !== majorVersion(WORKSPACE_CONTRACT_VERSION)) {
          emitWorkspaceTelemetry("workspace.unsupported_contract", {
            contract_version: result.contractVersion,
            session_id: sessionId,
            plan_etag: result.etag,
          });
          setErrorUiState("Error");
          setErrorView({
            code: "UNSUPPORTED_CONTRACT",
            httpStatus: 200,
            presentation: "retryable_error",
          });
          return previous ?? null;
        }

        const next = replaceWorkspaceSnapshot(previous, {
          plan: result.plan,
          etag: result.etag,
          contractVersion: result.contractVersion,
        }) as CachedPlan;

        etagRef.current = next.etag;
        setErrorView(null);
        setErrorUiState(null);
        return next;
      } catch (err) {
        const status = err instanceof WorkspaceApiError ? err.status : 0;
        const code = err instanceof WorkspaceApiError ? err.code : null;
        const mapped = mapWorkspaceError(code, status);
        setErrorView(mapped.error);
        if (mapped.uiState === "Forbidden" || mapped.uiState === "NotFound" || mapped.uiState === "Error") {
          setErrorUiState(mapped.uiState);
        }
        if (previous) {
          return previous;
        }
        throw err;
      }
    },
    refetchInterval: pollIntervalMs > 0 ? pollIntervalMs : false,
    refetchOnWindowFocus: true,
    retry: (failureCount) => failureCount < WORKSPACE_RETRY.maxAttempts,
    retryDelay: (attempt) => workspaceBackoffDelay(attempt),
    staleTime: 0,
  });

  const applyMutationSuccess = useCallback(
    (result: {
      plan: WorkspacePlanResponse;
      etag: string;
      contractVersion: string;
    }) => {
      const next = replaceWorkspaceSnapshot(null, {
        plan: result.plan,
        etag: result.etag,
        contractVersion: result.contractVersion,
      }) as CachedPlan;
      etagRef.current = next.etag;
      queryClient.setQueryData(queryKey, next);
      setErrorView(null);
      setErrorUiState(null);
    },
    [queryClient, queryKey],
  );

  const applyMutationError = useCallback(
    async (err: unknown) => {
      const status = err instanceof WorkspaceApiError ? err.status : 0;
      const code = err instanceof WorkspaceApiError ? err.code : null;
      const mapped = mapWorkspaceError(code, status);
      setErrorView(mapped.error);
      if (mapped.shouldRefetch) {
        await queryClient.invalidateQueries({ queryKey });
      }
      if (mapped.uiState === "Forbidden" || mapped.uiState === "NotFound" || mapped.uiState === "Error") {
        setErrorUiState(mapped.uiState);
      }
    },
    [queryClient, queryKey],
  );

  const acknowledgeMutation = useMutation({
    mutationFn: async (objectId: string) => {
      const current = queryClient.getQueryData<CachedPlan>(queryKey);
      if (!current?.etag) {
        throw new WorkspaceApiError("No plan etag for acknowledgement", 409, "WORKSPACE_PLAN_STALE");
      }
      return workspaceService.acknowledge(sessionId, { object_id: objectId }, current.etag);
    },
    onSuccess: applyMutationSuccess,
    onError: applyMutationError,
  });

  const refreshStoryMutation = useMutation({
    mutationFn: async () => {
      const current = queryClient.getQueryData<CachedPlan>(queryKey);
      if (!current?.etag) {
        throw new WorkspaceApiError("No plan etag for story refresh", 409, "WORKSPACE_PLAN_STALE");
      }
      return workspaceService.refreshStory(sessionId, current.etag);
    },
    onSuccess: (result) => {
      applyMutationSuccess(result);
      // Forward-compatible: poll story/status until ready/failed (sync today).
      setPollStoryStatus(true);
    },
    onError: applyMutationError,
  });

  const resolveMutation = useMutation({
    mutationFn: async (objectId: string) => {
      const current = queryClient.getQueryData<CachedPlan>(queryKey);
      if (!current?.etag) {
        throw new WorkspaceApiError("No plan etag for resolve", 409, "WORKSPACE_PLAN_STALE");
      }
      return workspaceService.resolve(sessionId, objectId, current.etag);
    },
    onSuccess: applyMutationSuccess,
    onError: applyMutationError,
  });

  const dismissMutation = useMutation({
    mutationFn: async (objectId: string) => {
      const current = queryClient.getQueryData<CachedPlan>(queryKey);
      if (!current?.etag) {
        throw new WorkspaceApiError("No plan etag for dismiss", 409, "WORKSPACE_PLAN_STALE");
      }
      return workspaceService.dismiss(sessionId, objectId, current.etag);
    },
    onSuccess: applyMutationSuccess,
    onError: applyMutationError,
  });

  useEffect(() => {
    if (!pollStoryStatus) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const status = await workspaceService.fetchStoryStatus(sessionId);
        if (cancelled) return;
        if (status.story_status === "ready" || status.story_status === "failed") {
          setPollStoryStatus(false);
          await queryClient.invalidateQueries({ queryKey });
        }
      } catch {
        if (!cancelled) setPollStoryStatus(false);
      }
    };
    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, STORY_STATUS_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [pollStoryStatus, queryClient, queryKey, sessionId]);

  const plan = query.data?.plan ?? null;
  const etag = query.data?.etag ?? null;

  const viewModel: WorkspaceViewModel | null = useMemo(() => {
    if (!plan || !etag) return null;
    return projectPlan(plan, etag);
  }, [plan, etag]);

  const isRefreshing =
    (query.isFetching && !!plan) ||
    acknowledgeMutation.isPending ||
    refreshStoryMutation.isPending ||
    resolveMutation.isPending ||
    dismissMutation.isPending ||
    pollStoryStatus;

  const uiState = deriveWorkspaceUiState({
    hasPlan: !!plan,
    workspaceState: plan?.workspace_state,
    isRefreshing,
    clientOffline: clientOffline || offline || plan?.workspace_state === "offline",
    errorUiState: plan ? null : errorUiState,
  });

  const acknowledge = useCallback(
    (objectId: string) => {
      if (!viewModel?.mutationsAllowed) return;
      acknowledgeMutation.mutate(objectId);
    },
    [acknowledgeMutation, viewModel?.mutationsAllowed],
  );

  const refreshStory = useCallback(() => {
    if (!viewModel?.mutationsAllowed) return;
    refreshStoryMutation.mutate();
  }, [refreshStoryMutation, viewModel?.mutationsAllowed]);

  const resolve = useCallback(
    (objectId: string) => {
      if (!viewModel?.mutationsAllowed) return;
      resolveMutation.mutate(objectId);
    },
    [resolveMutation, viewModel?.mutationsAllowed],
  );

  const dismiss = useCallback(
    (objectId: string) => {
      if (!viewModel?.mutationsAllowed) return;
      dismissMutation.mutate(objectId);
    },
    [dismissMutation, viewModel?.mutationsAllowed],
  );

  const retry = useCallback(() => {
    setErrorView(null);
    setErrorUiState(null);
    void query.refetch();
  }, [query]);

  return {
    uiState,
    viewModel,
    plan,
    etag,
    error: errorView,
    isTransportLoading: query.isLoading && !plan,
    isRefreshing,
    acknowledge,
    refreshStory,
    resolve,
    dismiss,
    retry,
    acknowledgePending: acknowledgeMutation.isPending,
    refreshStoryPending: refreshStoryMutation.isPending,
    resolvePending: resolveMutation.isPending,
    dismissPending: dismissMutation.isPending,
  };
}
