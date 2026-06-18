import { NextResponse } from "next/server";

function shouldUseSecureCookies(request: Request): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  return request.url.startsWith("https://") || forwardedProto === "https";
}

export async function POST(request: Request) {
  const res = NextResponse.json({ success: true });
  res.cookies.set("access_token", "", {
    httpOnly: true,
    secure: shouldUseSecureCookies(request),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return res;
}
