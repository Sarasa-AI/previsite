import { NextResponse } from "next/server";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";

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
