/**
 * Server-state cache helpers for Workspace plans.
 * React Query owns server state only — no presentation UI state here.
 */

export const WORKSPACE_QUERY_ROOT = "workspace" as const;

export type WorkspaceCacheKeyParams = {
  sessionId: number | string;
  lens: string;
  role: string;
};

export function workspaceQueryKey(params: WorkspaceCacheKeyParams) {
  return [WORKSPACE_QUERY_ROOT, String(params.sessionId), params.lens, params.role] as const;
}

export const CLINICAL_CONTENT_QUERY_ROOT = "clinical-content" as const;

export type ClinicalContentCacheKeyParams = {
  sessionId: number | string;
  contextHash?: string | null;
};

export function clinicalContentQueryKey(params: ClinicalContentCacheKeyParams) {
  return [
    CLINICAL_CONTENT_QUERY_ROOT,
    String(params.sessionId),
    params.contextHash ?? "",
  ] as const;
}

export type WorkspaceServerSnapshot = {
  plan: unknown;
  etag: string;
  contractVersion: string;
  lastCheckedAt: number;
};

/** Retry/backoff defaults for transport failures (server state only). */
export const WORKSPACE_RETRY = {
  maxAttempts: 3,
  baseDelayMs: 500,
  maxDelayMs: 8_000,
} as const;

export function workspaceBackoffDelay(attempt: number): number {
  const exp = Math.min(
    WORKSPACE_RETRY.maxDelayMs,
    WORKSPACE_RETRY.baseDelayMs * 2 ** Math.max(0, attempt),
  );
  return exp;
}

/**
 * Atomic replace rule: never merge plans from different ETags.
 * Returns the next snapshot only when etags differ or plan is new.
 */
export function replaceWorkspaceSnapshot(
  previous: WorkspaceServerSnapshot | null | undefined,
  next: Omit<WorkspaceServerSnapshot, "lastCheckedAt"> & { lastCheckedAt?: number },
): WorkspaceServerSnapshot {
  return {
    plan: next.plan,
    etag: next.etag,
    contractVersion: next.contractVersion,
    lastCheckedAt: next.lastCheckedAt ?? Date.now(),
  };
}

/**
 * On 304 Not Modified: keep previous plan/etag; update last-checked only.
 */
export function keepWorkspaceSnapshotOn304(
  previous: WorkspaceServerSnapshot,
): WorkspaceServerSnapshot {
  return {
    ...previous,
    lastCheckedAt: Date.now(),
  };
}

/**
 * Guard: refuse to merge fields across different ETags.
 */
export function assertSameEtagOrReplace(
  previousEtag: string | null | undefined,
  nextEtag: string,
): "keep" | "replace" {
  if (!previousEtag || previousEtag === nextEtag) {
    return previousEtag === nextEtag && previousEtag ? "keep" : "replace";
  }
  return "replace";
}
