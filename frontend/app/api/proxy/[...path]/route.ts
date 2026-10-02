import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import {
  clearAuthCookies,
  readAccessTokenFromRequest,
  readRefreshTokenFromRequest,
  setAuthCookiesFromTokenPayload,
} from "@/lib/auth-cookies";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = getBackendApiUrl();

/**
 * Transparent transport proxy only.
 * May forward request/response headers, status codes, and bodies.
 * Must never map DTOs, transform payloads, or inject presentation/business/clinical logic.
 * On backend 401: attempt exactly one refresh + retry; on failure clear both auth cookies.
 */
const FORWARD_REQUEST_HEADERS = ["If-None-Match", "If-Match", "Content-Type", "Accept"] as const;
const FORWARD_RESPONSE_HEADERS = [
  "ETag",
  "X-Contract-Version",
  "X-Request-ID",
  "Content-Type",
  "Content-Disposition",
] as const;

function copyRequestHeaders(request: Request, headers: Headers): void {
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
}

function copyResponseHeaders(response: Response, outHeaders: Headers): void {
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) outHeaders.set(name, value);
  }
}

async function readJsonFromResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/**
 * Attempt a single refresh against the backend. Returns new tokens or null.
 * Never loops — caller must invoke at most once per proxied request.
 */
async function tryRefreshTokens(
  request: Request,
): Promise<Record<string, unknown> | null> {
  const refreshToken = readRefreshTokenFromRequest(request);
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${BACKEND_API_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return null;
    const data = await readJsonFromResponse(response);
    if (!data || typeof data !== "object") return null;
    const record = data as Record<string, unknown>;
    if (
      typeof record.access_token !== "string" ||
      !record.access_token ||
      typeof record.refresh_token !== "string" ||
      !record.refresh_token
    ) {
      return null;
    }
    return record;
  } catch {
    return null;
  }
}

async function forwardOnce(
  request: Request,
  params: { path: string[] },
  accessToken: string | null,
  body: BodyInit | undefined,
  method: string,
): Promise<Response> {
  const path = params.path.join("/");
  const url = new URL(request.url);
  const target = `${BACKEND_API_URL}/${path}${url.search}`;

  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  copyRequestHeaders(request, headers);

  // FormData must not send a pre-set multipart boundary Content-Type.
  if (typeof FormData !== "undefined" && body instanceof FormData) {
    headers.delete("Content-Type");
  }

  return fetch(target, {
    method,
    headers,
    body,
  });
}

function toNextResponse(response: Response, bodyTextOrBuffer: string | ArrayBuffer, isText: boolean): NextResponse {
  const outHeaders = new Headers();
  copyResponseHeaders(response, outHeaders);
  if (isText) {
    const contentType = response.headers.get("content-type") || "application/json";
    if (!outHeaders.has("Content-Type")) {
      outHeaders.set("Content-Type", contentType);
    }
    return new NextResponse(bodyTextOrBuffer as string, {
      status: response.status,
      headers: outHeaders,
    });
  }
  return new NextResponse(bodyTextOrBuffer as ArrayBuffer, {
    status: response.status,
    headers: outHeaders,
  });
}

async function forward(request: Request, params: { path: string[] }) {
  const method = request.method.toUpperCase();
  let body: BodyInit | undefined;
  let bufferedText: string | undefined;
  let bufferedForm: FormData | undefined;

  if (method !== "GET" && method !== "HEAD") {
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      bufferedForm = await request.formData();
      body = bufferedForm;
    } else {
      bufferedText = await request.text();
      body = bufferedText;
    }
  }

  const initialToken = readAccessTokenFromRequest(request);
  let response = await forwardOnce(request, params, initialToken, body, method);

  let refreshedPayload: Record<string, unknown> | null = null;

  // Exactly one refresh + retry on 401 — never loop.
  if (response.status === 401) {
    refreshedPayload = await tryRefreshTokens(request);
    if (refreshedPayload) {
      const newAccess = refreshedPayload.access_token as string;
      // Re-use buffered body for the single retry.
      const retryBody =
        bufferedForm !== undefined
          ? bufferedForm
          : bufferedText !== undefined
            ? bufferedText
            : undefined;
      response = await forwardOnce(request, params, newAccess, retryBody, method);
    }
  }

  if (response.status === 304) {
    const outHeaders = new Headers();
    copyResponseHeaders(response, outHeaders);
    const nextResponse = new NextResponse(null, {
      status: 304,
      headers: outHeaders,
    });
    if (refreshedPayload) {
      setAuthCookiesFromTokenPayload(nextResponse, request, refreshedPayload);
    }
    return nextResponse;
  }

  const contentType = response.headers.get("content-type") || "application/json";
  const isTextResponse =
    contentType.includes("application/json") ||
    contentType.startsWith("text/") ||
    contentType.includes("application/problem+json");

  let nextResponse: NextResponse;
  if (!isTextResponse) {
    const buffer = await response.arrayBuffer();
    nextResponse = toNextResponse(response, buffer, false);
  } else {
    const text = await response.text();
    nextResponse = toNextResponse(response, text, true);
  }

  if (refreshedPayload && response.status !== 401) {
    setAuthCookiesFromTokenPayload(nextResponse, request, refreshedPayload);
  } else if (response.status === 401) {
    clearAuthCookies(nextResponse, request);
  }

  return nextResponse;
}

export async function GET(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function POST(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

// The backend exposes PATCH (e.g. PATCH /api/files/{session_id}/files/{file_id}) and
// PUT/DELETE. Without these handlers Next.js answers 405 before the proxy ever runs,
// which silently broke document↔condition unlinking from the intake UI.
export async function PATCH(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function PUT(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function DELETE(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function HEAD(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}
