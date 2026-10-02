import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import {
  clearAuthCookies,
  readRefreshTokenFromRequest,
} from "@/lib/auth-cookies";

process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

export const dynamic = "force-dynamic";

/**
 * Revoke current refresh family on the backend, then clear both auth cookies.
 * refresh_token is read from the httpOnly cookie and never returned to JS.
 */
export async function POST(request: Request) {
  const backendApiUrl = getBackendApiUrl();
  const refreshToken = readRefreshTokenFromRequest(request);

  if (refreshToken) {
    try {
      await fetch(`${backendApiUrl}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Still clear cookies locally if backend is unreachable.
    }
  }

  const res = NextResponse.json({ success: true });
  return clearAuthCookies(res, request);
}
