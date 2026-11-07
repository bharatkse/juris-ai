import { type NextRequest, NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
} from "@/lib/server/auth";

export function middleware(request: NextRequest): NextResponse {
  const hasAccessToken = Boolean(
    request.cookies.get(ACCESS_TOKEN_COOKIE)?.value,
  );
  const hasRefreshToken = Boolean(
    request.cookies.get(REFRESH_TOKEN_COOKIE)?.value,
  );

  if (hasAccessToken || hasRefreshToken) {
    return NextResponse.next();
  }

  const login = request.nextUrl.clone();
  login.pathname = "/login";
  login.search = "";
  login.searchParams.set(
    "next",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );

  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/app/:path*"],
};
