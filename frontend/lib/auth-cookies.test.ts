/** @vitest-environment node */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { NextResponse } from "next/server";

import {
  cookieMaxAgeFromExpiresIn,
  FALLBACK_TOKEN_MAX_AGE_SECONDS,
  FALLBACK_REFRESH_MAX_AGE_SECONDS,
  setAccessTokenCookie,
  setRefreshTokenCookie,
  setAuthCookiesFromTokenPayload,
  clearAccessTokenCookie,
  clearRefreshTokenCookie,
  clearAuthCookies,
  readRefreshTokenFromRequest,
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
} from "@/lib/auth-cookies";

describe("cookieMaxAgeFromExpiresIn", () => {
  it("uses backend expires_in seconds when valid", () => {
    expect(cookieMaxAgeFromExpiresIn(900)).toBe(900);
    expect(cookieMaxAgeFromExpiresIn(3600.9)).toBe(3600);
  });

  it("falls back for missing or invalid lifetimes", () => {
    expect(cookieMaxAgeFromExpiresIn(undefined)).toBe(FALLBACK_TOKEN_MAX_AGE_SECONDS);
    expect(cookieMaxAgeFromExpiresIn(null)).toBe(FALLBACK_TOKEN_MAX_AGE_SECONDS);
    expect(cookieMaxAgeFromExpiresIn(0)).toBe(FALLBACK_TOKEN_MAX_AGE_SECONDS);
    expect(cookieMaxAgeFromExpiresIn(-10)).toBe(FALLBACK_TOKEN_MAX_AGE_SECONDS);
    expect(cookieMaxAgeFromExpiresIn("1800")).toBe(FALLBACK_TOKEN_MAX_AGE_SECONDS);
  });

  it("accepts a custom fallback for refresh cookies", () => {
    expect(cookieMaxAgeFromExpiresIn(undefined, FALLBACK_REFRESH_MAX_AGE_SECONDS)).toBe(
      FALLBACK_REFRESH_MAX_AGE_SECONDS,
    );
  });

  it("never exceeds the provided JWT lifetime when valid", () => {
    const jwtLifetime = 15 * 60;
    const maxAge = cookieMaxAgeFromExpiresIn(jwtLifetime);
    expect(maxAge).toBeLessThanOrEqual(jwtLifetime);
  });
});

describe("setAccessTokenCookie / setRefreshTokenCookie", () => {
  it("sets access maxAge from expires_in", () => {
    const request = new Request("http://localhost/api/auth/login");
    const res = NextResponse.json({ success: true });
    setAccessTokenCookie(res, request, "tok", 900);
    const cookie = res.cookies.get(ACCESS_TOKEN_COOKIE);
    expect(cookie?.value).toBe("tok");
    expect(cookie?.httpOnly).toBe(true);
    const setCookie = res.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/Max-Age=900/i);
  });

  it("sets refresh_token as httpOnly with refresh_expires_in", () => {
    const request = new Request("http://localhost/api/auth/login");
    const res = NextResponse.json({ success: true });
    setRefreshTokenCookie(res, request, "refresh-raw", 3600);
    const cookie = res.cookies.get(REFRESH_TOKEN_COOKIE);
    expect(cookie?.value).toBe("refresh-raw");
    expect(cookie?.httpOnly).toBe(true);
    const setCookie = res.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/refresh_token=/i);
    expect(setCookie.join(";")).toMatch(/Max-Age=3600/i);
  });

  it("setAuthCookiesFromTokenPayload sets both cookies", () => {
    const request = new Request("http://localhost/api/auth/login");
    const res = NextResponse.json({ success: true });
    setAuthCookiesFromTokenPayload(res, request, {
      access_token: "a",
      expires_in: 900,
      refresh_token: "r",
      refresh_expires_in: 3600,
    });
    expect(res.cookies.get(ACCESS_TOKEN_COOKIE)?.value).toBe("a");
    expect(res.cookies.get(REFRESH_TOKEN_COOKIE)?.value).toBe("r");
  });
});

describe("readRefreshTokenFromRequest", () => {
  it("reads refresh_token from Cookie header", () => {
    const request = new Request("http://localhost/api/auth/refresh", {
      headers: { cookie: "access_token=a; refresh_token=secret.raw" },
    });
    expect(readRefreshTokenFromRequest(request)).toBe("secret.raw");
  });
});

describe("GET /api/auth/me", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns authenticated false and does not call backend without cookie", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    vi.doMock("@/lib/backend-config", () => ({
      getBackendApiUrl: () => "http://backend.test",
    }));

    const { GET } = await import("@/app/api/auth/me/route");
    const response = await GET(new Request("http://localhost/api/auth/me"));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ authenticated: false });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails closed on invalid/expired backend token (401)", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "unauthorized" }), { status: 401 }),
    ) as unknown as typeof fetch;

    vi.doMock("@/lib/backend-config", () => ({
      getBackendApiUrl: () => "http://backend.test",
    }));

    const { GET } = await import("@/app/api/auth/me/route");
    const request = new Request("http://localhost/api/auth/me", {
      headers: { cookie: "access_token=bad.jwt.token" },
    });
    const response = await GET(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ authenticated: false });
    const setCookie = response.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/access_token=/i);
    expect(setCookie.join(";")).toMatch(/refresh_token=/i);
  });

  it("returns backend-verified identity on success", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 7,
          role: "patient",
          display_name: "بیمار",
        }),
        { status: 200 },
      ),
    ) as unknown as typeof fetch;

    vi.doMock("@/lib/backend-config", () => ({
      getBackendApiUrl: () => "http://backend.test",
    }));

    const { GET } = await import("@/app/api/auth/me/route");
    const request = new Request("http://localhost/api/auth/me", {
      headers: { cookie: "access_token=good.token" },
    });
    const response = await GET(request);
    expect(await response.json()).toEqual({
      authenticated: true,
      id: 7,
      role: "patient",
      display_name: "بیمار",
    });
  });
});

describe("proxy single refresh retry on 401", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.resetModules();
  });

  it("refreshes once then retries the original request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "new-access",
            expires_in: 900,
            refresh_token: "new-refresh",
            refresh_expires_in: 3600,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    vi.doMock("@/lib/backend-config", () => ({
      getBackendApiUrl: () => "http://backend.test",
    }));

    const { GET } = await import("@/app/api/proxy/[...path]/route");
    const request = new Request("http://localhost/api/proxy/api/chat/sessions", {
      headers: {
        cookie: "access_token=stale.token; refresh_token=still.valid",
      },
    });
    const response = await GET(request, {
      params: { path: ["api", "chat", "sessions"] },
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const refreshCall = fetchMock.mock.calls[1];
    expect(String(refreshCall[0])).toContain("/api/auth/refresh");

    const setCookie = response.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/access_token=new-access/i);
    expect(setCookie.join(";")).toMatch(/refresh_token=new-refresh/i);
  });

  it("clears both cookies when refresh fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "bad refresh" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      );

    globalThis.fetch = fetchMock as unknown as typeof fetch;

    vi.doMock("@/lib/backend-config", () => ({
      getBackendApiUrl: () => "http://backend.test",
    }));

    const { GET } = await import("@/app/api/proxy/[...path]/route");
    const request = new Request("http://localhost/api/proxy/api/chat/sessions", {
      headers: {
        cookie: "access_token=stale.token; refresh_token=bad.refresh",
      },
    });
    const response = await GET(request, {
      params: { path: ["api", "chat", "sessions"] },
    });
    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const setCookie = response.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/access_token=/i);
    expect(setCookie.join(";")).toMatch(/refresh_token=/i);
    expect(setCookie.join(";")).toMatch(/Max-Age=0/i);
  });
});

describe("clearAuthCookies", () => {
  it("clears both cookies with maxAge 0", () => {
    const request = new Request("http://localhost/api/auth/logout");
    const res = NextResponse.json({ success: true });
    clearAuthCookies(res, request);
    const setCookie = res.headers.getSetCookie?.() ?? [];
    const joined = setCookie.join(";");
    expect(joined).toMatch(/access_token=/i);
    expect(joined).toMatch(/refresh_token=/i);
    expect(joined).toMatch(/Max-Age=0/i);
  });
});

describe("clearAccessTokenCookie / clearRefreshTokenCookie", () => {
  it("sets maxAge 0 individually", () => {
    const request = new Request("http://localhost/api/auth/logout");
    const res = NextResponse.json({ success: true });
    clearAccessTokenCookie(res, request);
    clearRefreshTokenCookie(res, request);
    const setCookie = res.headers.getSetCookie?.() ?? [];
    expect(setCookie.join(";")).toMatch(/Max-Age=0/i);
  });
});
