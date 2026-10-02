/**
 * Shared httpOnly auth cookie helpers for BFF routes.
 *
 * access_token — short-lived JWT (lifetime from backend expires_in).
 * refresh_token — opaque rotating token; must NEVER be readable by JS.
 * Cookie lifetime must never exceed the backend-reported lifetime.
 */

import { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

/** Conservative fallback only when backend omits expires_in (should not happen). */
export const FALLBACK_TOKEN_MAX_AGE_SECONDS = 15 * 60;

/** Fallback when backend omits refresh_expires_in (idle default: 60 minutes). */
export const FALLBACK_REFRESH_MAX_AGE_SECONDS = 60 * 60;

export function shouldUseSecureCookies(request: Request): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  return request.url.startsWith("https://") || forwardedProto === "https";
}

/**
 * Derive cookie maxAge from backend lifetime seconds.
 * Rejects non-positive / non-finite values so we never set an unbounded cookie.
 */
export function cookieMaxAgeFromExpiresIn(
  expiresIn: unknown,
  fallback: number = FALLBACK_TOKEN_MAX_AGE_SECONDS,
): number {
  if (typeof expiresIn !== "number" || !Number.isFinite(expiresIn)) {
    return fallback;
  }
  const seconds = Math.floor(expiresIn);
  if (seconds <= 0) {
    return fallback;
  }
  return seconds;
}

function readCookieValue(request: Request, name: string): string | null {
  const header = request.headers.get("cookie");
  if (!header) return null;
  const match = header.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  const raw = match?.[1];
  if (!raw) return null;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

export function readAccessTokenFromRequest(request: Request): string | null {
  return readCookieValue(request, ACCESS_TOKEN_COOKIE);
}

export function readRefreshTokenFromRequest(request: Request): string | null {
  return readCookieValue(request, REFRESH_TOKEN_COOKIE);
}

export function setAccessTokenCookie(
  response: NextResponse,
  request: Request,
  token: string,
  expiresIn: unknown,
): NextResponse {
  response.cookies.set(ACCESS_TOKEN_COOKIE, token, {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: cookieMaxAgeFromExpiresIn(expiresIn),
  });
  return response;
}

export function setRefreshTokenCookie(
  response: NextResponse,
  request: Request,
  token: string,
  refreshExpiresIn: unknown,
): NextResponse {
  response.cookies.set(REFRESH_TOKEN_COOKIE, token, {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: cookieMaxAgeFromExpiresIn(
      refreshExpiresIn,
      FALLBACK_REFRESH_MAX_AGE_SECONDS,
    ),
  });
  return response;
}

/**
 * Set both auth cookies from a backend token-pair JSON payload.
 * Strips tokens from any client-visible body — callers should return
 * { success: true } (or MFA backup codes) without refresh_token.
 */
export function setAuthCookiesFromTokenPayload(
  response: NextResponse,
  request: Request,
  payload: Record<string, unknown>,
): NextResponse {
  const access = payload.access_token;
  if (typeof access === "string" && access) {
    setAccessTokenCookie(response, request, access, payload.expires_in);
  }
  const refresh = payload.refresh_token;
  if (typeof refresh === "string" && refresh) {
    setRefreshTokenCookie(
      response,
      request,
      refresh,
      payload.refresh_expires_in,
    );
  }
  return response;
}

export function clearAccessTokenCookie(
  response: NextResponse,
  request: Request,
): NextResponse {
  response.cookies.set(ACCESS_TOKEN_COOKIE, "", {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}

export function clearRefreshTokenCookie(
  response: NextResponse,
  request: Request,
): NextResponse {
  response.cookies.set(REFRESH_TOKEN_COOKIE, "", {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}

export function clearAuthCookies(
  response: NextResponse,
  request: Request,
): NextResponse {
  clearAccessTokenCookie(response, request);
  clearRefreshTokenCookie(response, request);
  return response;
}
