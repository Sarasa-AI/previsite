import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import { setAuthCookiesFromTokenPayload } from "@/lib/auth-cookies";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

export const dynamic = "force-dynamic";

async function readJsonFromResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

export async function POST(request: Request) {
  const backendApiUrl = getBackendApiUrl();

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  let response: Response;
  try {
    response = await fetch(`${backendApiUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    console.error("Login failed with error:", error);
    return NextResponse.json(
      { detail: "Backend is unreachable", error: String(error) },
      { status: 502 },
    );
  }

  const data = (await readJsonFromResponse(response)) as unknown;
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }

  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (record.mfa_required === true || record.mfa_setup_required === true) {
      return NextResponse.json(data);
    }
    if (record.phone_link_required === true) {
      // Legacy patient must complete OTP phone link — no cookies yet.
      return NextResponse.json(data);
    }
    const token = record.access_token;
    if (typeof token === "string" && token) {
      // Never forward refresh_token to the browser JS bundle.
      const res = NextResponse.json({ success: true });
      return setAuthCookiesFromTokenPayload(res, request, record);
    }
  }

  return NextResponse.json(
    { detail: "Invalid login response from backend" },
    { status: 502 },
  );
}
