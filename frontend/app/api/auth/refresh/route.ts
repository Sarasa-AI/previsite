import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import {
  clearAuthCookies,
  readRefreshTokenFromRequest,
  setAuthCookiesFromTokenPayload,
} from "@/lib/auth-cookies";

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

/**
 * Rotate refresh token + issue new access JWT.
 * Tokens are set as httpOnly cookies only — never returned in the JSON body.
 */
export async function POST(request: Request) {
  const refreshToken = readRefreshTokenFromRequest(request);
  if (!refreshToken) {
    const res = NextResponse.json(
      { detail: "No refresh token" },
      { status: 401 },
    );
    return clearAuthCookies(res, request);
  }

  const backendApiUrl = getBackendApiUrl();
  let response: Response;
  try {
    response = await fetch(`${backendApiUrl}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch (error) {
    const res = NextResponse.json(
      { detail: "Backend is unreachable", error: String(error) },
      { status: 502 },
    );
    return clearAuthCookies(res, request);
  }

  const data = await readJsonFromResponse(response);
  if (!response.ok) {
    const res = NextResponse.json(data, { status: response.status });
    return clearAuthCookies(res, request);
  }

  const record =
    data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  const access = record?.access_token;
  const refresh = record?.refresh_token;
  if (typeof access !== "string" || !access || typeof refresh !== "string" || !refresh) {
    const res = NextResponse.json(
      { detail: "Invalid refresh response from backend" },
      { status: 502 },
    );
    return clearAuthCookies(res, request);
  }

  const res = NextResponse.json({ success: true });
  return setAuthCookiesFromTokenPayload(res, request, record);
}
