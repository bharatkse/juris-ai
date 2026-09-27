import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  authenticatedBackendFetch,
  bffError,
  clearSessionCookies,
  REFRESH_TOKEN_COOKIE,
  relayBackendResponse,
  serviceUnavailable,
  setSessionCookies,
} from "@/lib/server/auth";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return bffError(401, "UNAUTHORIZED", "Please sign in to continue.");
  }

  try {
    const result = await authenticatedBackendFetch({
      path: "/auth/me",
      accessToken,
      refreshToken,
      init: { method: "GET", headers: { Accept: "application/json" } },
    });
    const response = await relayBackendResponse(result.response);

    if (result.refreshedTokens) {
      setSessionCookies(response, result.refreshedTokens);
    }
    if (result.clearSession) {
      clearSessionCookies(response);
    }

    return response;
  } catch {
    return serviceUnavailable();
  }
}
