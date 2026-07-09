import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = getBackendApiUrl();

async function forward(request: Request, params: { path: string[] }) {
  const path = params.path.join("/");
  const token = request.headers.get("cookie")?.match(/access_token=([^;]+)/)?.[1];
  const target = `${BACKEND_API_URL}/${path}`;

  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${decodeURIComponent(token)}`);

  const method = request.method.toUpperCase();
  let body: BodyInit | undefined;

  if (method !== "GET" && method !== "HEAD") {
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      body = await request.formData();
    } else {
      headers.set("Content-Type", "application/json");
      body = await request.text();
    }
  }

  const response = await fetch(target, {
    method,
    headers,
    body,
  });

  const contentType = response.headers.get("content-type") || "application/json";
  const isTextResponse =
    contentType.includes("application/json") ||
    contentType.startsWith("text/") ||
    contentType.includes("application/problem+json");

  if (!isTextResponse) {
    const buffer = await response.arrayBuffer();
    const outHeaders = new Headers();
    outHeaders.set("Content-Type", contentType);
    const disposition = response.headers.get("content-disposition");
    if (disposition) {
      outHeaders.set("Content-Disposition", disposition);
    }
    return new NextResponse(buffer, {
      status: response.status,
      headers: outHeaders,
    });
  }

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") || "application/json",
    },
  });
}

export async function GET(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}

export async function POST(request: Request, { params }: { params: { path: string[] } }) {
  return forward(request, params);
}
