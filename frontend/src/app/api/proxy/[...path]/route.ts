import { NextResponse } from "next/server";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

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
