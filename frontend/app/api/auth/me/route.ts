import { NextResponse } from "next/server";
import { getBackendApiUrl } from "@/lib/backend-config";
import {
  clearAuthCookies,
  readAccessTokenFromRequest,
} from "@/lib/auth-cookies";

export const dynamic = "force-dynamic";

/**
 * Backend-verified current user. Never decode JWT locally without verification.
 */
export async function GET(request: Request) {
  const token = readAccessTokenFromRequest(request);
  if (!token) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  const backendApiUrl = getBackendApiUrl();
  let response: Response;
  try {
    response = await fetch(`${backendApiUrl}/api/auth/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  if (response.status === 401 || response.status === 403) {
    const res = NextResponse.json({ authenticated: false }, { status: 200 });
    return clearAuthCookies(res, request);
  }

  if (!response.ok) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  if (!data || typeof data !== "object") {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  const record = data as Record<string, unknown>;
  return NextResponse.json({
    authenticated: true,
    id: record.id,
    role: record.role,
    display_name: record.display_name,
  });
}
