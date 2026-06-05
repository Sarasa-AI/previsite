import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// نکته آموزشی:
// از آن‌جا که JWT داخل کوکی httpOnly قرار دارد، این لایه سروری می‌تواند
// بدون نشت توکن به مرورگر، مسیرهای حساس را خیلی زود کنترل کند و از فلاش
// خوردن صفحه‌ی محافظت‌شده پیش از redirect جلوگیری کند.
export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/chat/:path*", "/upload/:path*", "/summary/:path*", "/intake/:path*", "/clinician/:path*"],
};
