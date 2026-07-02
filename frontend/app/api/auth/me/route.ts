import { NextResponse } from "next/server";

function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return Buffer.from(padded, "base64").toString("utf-8");
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length < 2) return null;
  try {
    const payloadJson = base64UrlDecode(parts[1] ?? "");
    const parsed = JSON.parse(payloadJson) as Record<string, unknown>;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  const token = request.headers.get("cookie")?.match(/access_token=([^;]+)/)?.[1];
  if (!token) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  const payload = decodeJwtPayload(decodeURIComponent(token));
  const sub = payload?.sub;
  const userId = typeof sub === "string" && sub.trim() ? Number(sub) : null;
  if (!userId || Number.isNaN(userId)) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  return NextResponse.json({ authenticated: true, user_id: userId }, { status: 200 });
}

