import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import {
  clearAuthCookies,
  readAccessTokenFromRequest,
} from "@/lib/auth-cookies";

process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

export const dynamic = "force-dynamic";

/**
 * Revoke all refresh-token families for the authenticated user, then clear cookies.
 */
export async function POST(request: Request) {
  const backendApiUrl = getBackendApiUrl();
  const accessToken = readAccessTokenFromRequest(request);

  if (accessToken) {
    try {
      await fetch(`${backendApiUrl}/api/auth/logout-all`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
    } catch {
      // Still clear cookies locally.
    }
  }

  const res = NextResponse.json({ success: true });
  return clearAuthCookies(res, request);
}
