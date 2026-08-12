/**
 * Transparent transport header helpers for Workspace conditional requests.
 * No DTO mapping or payload transformation.
 */

export const WORKSPACE_REQUEST_HEADERS = {
  IF_NONE_MATCH: "If-None-Match",
  IF_MATCH: "If-Match",
} as const;

export const WORKSPACE_RESPONSE_HEADERS = {
  ETAG: "ETag",
  CONTRACT_VERSION: "X-Contract-Version",
  REQUEST_ID: "X-Request-ID",
} as const;

export function readHeader(
  headers: Headers | Record<string, string | undefined> | undefined,
  name: string,
): string | null {
  if (!headers) return null;
  if (headers instanceof Headers) {
    return headers.get(name) ?? headers.get(name.toLowerCase());
  }
  const direct = headers[name] ?? headers[name.toLowerCase()];
  return typeof direct === "string" && direct.length > 0 ? direct : null;
}

export function stripWeakEtag(etag: string | null | undefined): string | null {
  if (!etag) return null;
  const trimmed = etag.trim();
  if (trimmed.startsWith("W/")) {
    return trimmed.slice(2).trim().replace(/^"|"$/g, "") || null;
  }
  return trimmed.replace(/^"|"$/g, "") || null;
}
