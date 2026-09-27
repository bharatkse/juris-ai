import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  bffError,
  clearSessionCookies,
  fetchBackend,
  isSameOriginRequest,
} from "@/lib/server/auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  if (!isSameOriginRequest(request)) {
    return bffError(403, "FORBIDDEN", "Cross-origin requests are not allowed.");
  }

  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;

  if (accessToken) {
    try {
      await fetchBackend(
        "/auth/logout",
        { method: "POST", headers: { Accept: "application/json" } },
        accessToken,
      );
    } catch {
      // Local logout must succeed even when the API is unavailable.
    }
  }

  const response = NextResponse.json(
    {
      success: true,
      data: { authenticated: false },
      message: "Logged out.",
      metadata: {},
    },
    { headers: { "Cache-Control": "no-store" } },
  );
  clearSessionCookies(response);
  return response;
}
