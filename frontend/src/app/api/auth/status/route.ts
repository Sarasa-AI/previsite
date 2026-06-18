import { NextResponse } from "next/server";

// Bypass system proxies for local requests
process.env.NO_PROXY = "localhost,127.0.0.1";
process.env.no_proxy = "localhost,127.0.0.1";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  const token = request.headers.get("cookie")?.match(/access_token=([^;]+)/)?.[1];
  if (!token) {
    return NextResponse.json({ authenticated: false });
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/api/chat/sessions`, {
      headers: {
        Authorization: `Bearer ${decodeURIComponent(token)}`,
      },
      cache: "no-store",
    });
    return NextResponse.json({ authenticated: response.ok });
  } catch {
    return NextResponse.json({ authenticated: false });
  }
}
