/**
 * Typed Workspace API client.
 * Consumes only contract endpoints. No clinical or presentation logic.
 */

import {
  readHeader,
  stripWeakEtag,
  WORKSPACE_REQUEST_HEADERS,
  WORKSPACE_RESPONSE_HEADERS,
} from "@/src/shared/api/headers";
import type {
  AcknowledgementRequest,
  ClinicalContentResponse,
  DecisionTraceResponse,
  StoryStatusResponse,
  WorkspacePlanResponse,
  WorkspacePlanResult,
  WorkspaceQueryParams,
} from "./types";

const PROXY_PREFIX = "/api/proxy";

export class WorkspaceApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string | null,
    public readonly body: unknown = null,
  ) {
    super(message);
    this.name = "WorkspaceApiError";
  }
}

function buildQuery(params?: WorkspaceQueryParams): string {
  const search = new URLSearchParams();
  if (params?.lens) search.set("lens", params.lens);
  if (params?.role) search.set("role", params.role);
  if (params?.offline === true) search.set("offline", "true");
  if (params?.offline === false) search.set("offline", "false");
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function workspacePath(sessionId: number | string, suffix = ""): string {
  return `${PROXY_PREFIX}/api/sessions/${sessionId}/workspace${suffix}`;
}

async function parseJsonSafe(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function extractErrorCode(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

function resolveEtag(
  headers: Headers,
  planEtag: string | undefined,
): string {
  const headerEtag = stripWeakEtag(readHeader(headers, WORKSPACE_RESPONSE_HEADERS.ETAG));
  if (headerEtag && planEtag && headerEtag !== planEtag) {
    // Prefer header per presentation §9.1
    return headerEtag;
  }
  return headerEtag ?? planEtag ?? "";
}

async function throwIfNotOk(response: Response): Promise<void> {
  if (response.ok || response.status === 304) return;
  const body = await parseJsonSafe(response);
  const code = extractErrorCode(body);
  throw new WorkspaceApiError(
    code ?? `Workspace request failed (${response.status})`,
    response.status,
    code,
    body,
  );
}

export type GetWorkspaceOptions = {
  ifNoneMatch?: string;
  signal?: AbortSignal;
};

export async function getWorkspace(
  sessionId: number | string,
  params?: WorkspaceQueryParams,
  options?: GetWorkspaceOptions,
): Promise<WorkspacePlanResult> {
  const headers = new Headers();
  if (options?.ifNoneMatch) {
    headers.set(WORKSPACE_REQUEST_HEADERS.IF_NONE_MATCH, options.ifNoneMatch);
  }

  const response = await fetch(`${workspacePath(sessionId)}${buildQuery(params)}`, {
    method: "GET",
    credentials: "include",
    headers,
    signal: options?.signal,
  });

  if (response.status === 304) {
    const etag =
      stripWeakEtag(readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.ETAG)) ??
      options?.ifNoneMatch ??
      "";
    return {
      notModified: true,
      etag,
      contractVersion: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION),
      requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
    };
  }

  await throwIfNotOk(response);
  const body = (await parseJsonSafe(response)) as WorkspacePlanResponse;
  const etag = resolveEtag(response.headers, body.plan_etag);
  return {
    notModified: false,
    plan: body,
    etag,
    contractVersion:
      readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION) ??
      body.contract_version,
    requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
  };
}

export async function getWorkspaceTrace(
  sessionId: number | string,
  params?: WorkspaceQueryParams,
  options?: { signal?: AbortSignal },
): Promise<{
  trace: DecisionTraceResponse;
  etag: string;
  contractVersion: string | null;
}> {
  const response = await fetch(
    `${workspacePath(sessionId, "/trace")}${buildQuery(params)}`,
    {
      method: "GET",
      credentials: "include",
      signal: options?.signal,
    },
  );
  await throwIfNotOk(response);
  const body = (await parseJsonSafe(response)) as DecisionTraceResponse;
  return {
    trace: body,
    etag: resolveEtag(response.headers, body.plan_etag),
    contractVersion: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION),
  };
}

export async function acknowledgeWorkspaceObject(
  sessionId: number | string,
  body: AcknowledgementRequest,
  ifMatch: string,
  options?: { signal?: AbortSignal },
): Promise<Extract<WorkspacePlanResult, { notModified: false }>> {
  const headers = new Headers({
    "Content-Type": "application/json",
    [WORKSPACE_REQUEST_HEADERS.IF_MATCH]: ifMatch,
  });
  const response = await fetch(`${workspacePath(sessionId, "/acknowledgements")}`, {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify(body),
    signal: options?.signal,
  });
  await throwIfNotOk(response);
  const plan = (await parseJsonSafe(response)) as WorkspacePlanResponse;
  return {
    notModified: false,
    plan,
    etag: resolveEtag(response.headers, plan.plan_etag),
    contractVersion:
      readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION) ??
      plan.contract_version,
    requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
  };
}

export async function refreshWorkspaceStory(
  sessionId: number | string,
  ifMatch: string,
  options?: { signal?: AbortSignal },
): Promise<Extract<WorkspacePlanResult, { notModified: false }>> {
  const headers = new Headers({
    "Content-Type": "application/json",
    [WORKSPACE_REQUEST_HEADERS.IF_MATCH]: ifMatch,
  });
  const response = await fetch(`${workspacePath(sessionId, "/story/refresh")}`, {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify({}),
    signal: options?.signal,
  });
  await throwIfNotOk(response);
  const plan = (await parseJsonSafe(response)) as WorkspacePlanResponse;
  return {
    notModified: false,
    plan,
    etag: resolveEtag(response.headers, plan.plan_etag),
    contractVersion:
      readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION) ??
      plan.contract_version,
    requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
  };
}

export async function resolveWorkspaceObject(
  sessionId: number | string,
  objectId: string,
  ifMatch: string,
  options?: { signal?: AbortSignal },
): Promise<Extract<WorkspacePlanResult, { notModified: false }>> {
  const headers = new Headers({
    "Content-Type": "application/json",
    [WORKSPACE_REQUEST_HEADERS.IF_MATCH]: ifMatch,
  });
  const response = await fetch(
    `${workspacePath(sessionId, `/decision-items/${encodeURIComponent(objectId)}/resolve`)}`,
    {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify({}),
      signal: options?.signal,
    },
  );
  await throwIfNotOk(response);
  const plan = (await parseJsonSafe(response)) as WorkspacePlanResponse;
  return {
    notModified: false,
    plan,
    etag: resolveEtag(response.headers, plan.plan_etag),
    contractVersion:
      readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION) ??
      plan.contract_version,
    requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
  };
}

export async function dismissWorkspaceObject(
  sessionId: number | string,
  objectId: string,
  ifMatch: string,
  options?: { signal?: AbortSignal },
): Promise<Extract<WorkspacePlanResult, { notModified: false }>> {
  const headers = new Headers({
    "Content-Type": "application/json",
    [WORKSPACE_REQUEST_HEADERS.IF_MATCH]: ifMatch,
  });
  const response = await fetch(
    `${workspacePath(sessionId, `/decision-items/${encodeURIComponent(objectId)}/dismiss`)}`,
    {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify({}),
      signal: options?.signal,
    },
  );
  await throwIfNotOk(response);
  const plan = (await parseJsonSafe(response)) as WorkspacePlanResponse;
  return {
    notModified: false,
    plan,
    etag: resolveEtag(response.headers, plan.plan_etag),
    contractVersion:
      readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.CONTRACT_VERSION) ??
      plan.contract_version,
    requestId: readHeader(response.headers, WORKSPACE_RESPONSE_HEADERS.REQUEST_ID),
  };
}

export async function getStoryStatus(
  sessionId: number | string,
  options?: { signal?: AbortSignal },
): Promise<StoryStatusResponse> {
  const response = await fetch(`${workspacePath(sessionId, "/story/status")}`, {
    method: "GET",
    credentials: "include",
    signal: options?.signal,
  });
  await throwIfNotOk(response);
  return (await parseJsonSafe(response)) as StoryStatusResponse;
}

function clinicalContentPath(sessionId: number | string): string {
  return `${PROXY_PREFIX}/api/sessions/${sessionId}/clinical-content`;
}

export async function getClinicalContent(
  sessionId: number | string,
  options?: { signal?: AbortSignal },
): Promise<ClinicalContentResponse> {
  const response = await fetch(clinicalContentPath(sessionId), {
    method: "GET",
    credentials: "include",
    signal: options?.signal,
  });
  await throwIfNotOk(response);
  return (await parseJsonSafe(response)) as ClinicalContentResponse;
}

export const workspaceClient = {
  getWorkspace,
  getWorkspaceTrace,
  getClinicalContent,
  acknowledgeWorkspaceObject,
  refreshWorkspaceStory,
  resolveWorkspaceObject,
  dismissWorkspaceObject,
  getStoryStatus,
};
