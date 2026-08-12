import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = getBackendApiUrl();

/**
 * Transparent transport proxy only.
 * May forward request/response headers, status codes, and bodies.
 * Must never map DTOs, transform payloads, or inject presentation/business/clinical logic.
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

async function forward(request: Request, params: { path: string[] }) {
  const path = params.path.join("/");
  const token = request.headers.get("cookie")?.match(/access_token=([^;]+)/)?.[1];
  const url = new URL(request.url);
  const target = `${BACKEND_API_URL}/${path}${url.search}`;

  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${decodeURIComponent(token)}`);
  copyRequestHeaders(request, headers);

  const method = request.method.toUpperCase();
  let body: BodyInit | undefined;

  if (method !== "GET" && method !== "HEAD") {
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      body = await request.formData();
      headers.delete("Content-Type");
    } else {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      body = await request.text();
    }
  }

  const response = await fetch(target, {
    method,
    headers,
    body,
  });

  const outHeaders = new Headers();
  copyResponseHeaders(response, outHeaders);

  // Preserve 304 with empty body (conditional GET).
  if (response.status === 304) {
    return new NextResponse(null, {
      status: 304,
      headers: outHeaders,
    });
  }

  const contentType = response.headers.get("content-type") || "application/json";
  const isTextResponse =
    contentType.includes("application/json") ||
    contentType.startsWith("text/") ||
    contentType.includes("application/problem+json");

  if (!isTextResponse) {
    const buffer = await response.arrayBuffer();
    return new NextResponse(buffer, {
      status: response.status,
      headers: outHeaders,
    });
  }

  const text = await response.text();
  if (!outHeaders.has("Content-Type")) {
    outHeaders.set("Content-Type", contentType);
  }
  return new NextResponse(text, {
    status: response.status,
    headers: outHeaders,
  });
}

export async function GET(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function POST(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}
