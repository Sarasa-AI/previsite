import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import { setAuthCookiesFromTokenPayload } from "@/lib/auth-cookies";

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
    response = await fetch(`${backendApiUrl}/api/auth/otp/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
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
    const token = record.access_token;
    if (typeof token === "string" && token) {
      const res = NextResponse.json({ success: true });
      return setAuthCookiesFromTokenPayload(res, request, record);
    }
  }

  return NextResponse.json(
    { detail: "Invalid OTP verify response from backend" },
    { status: 502 },
  );
}
