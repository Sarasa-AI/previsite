import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = getBackendApiUrl();

async function readJsonFromResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

function shouldUseSecureCookies(request: Request): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  return request.url.startsWith("https://") || forwardedProto === "https";
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  let response: Response;
  try {
    console.log("Attempting login to backend:", `${BACKEND_API_URL}/api/auth/login`);
    response = await fetch(`${BACKEND_API_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    console.error("Login failed with error:", error);
    return NextResponse.json({ detail: "Backend is unreachable", error: String(error) }, { status: 502 });
  }

  const data = (await readJsonFromResponse(response)) as unknown;
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }

  const token =
    data && typeof data === "object" && "access_token" in data ? (data as { access_token?: unknown }).access_token : undefined;
  if (typeof token !== "string" || !token) {
    return NextResponse.json({ detail: "Invalid login response from backend" }, { status: 502 });
  }

  const res = NextResponse.json({ success: true });
  res.cookies.set("access_token", token, {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  return res;
}
