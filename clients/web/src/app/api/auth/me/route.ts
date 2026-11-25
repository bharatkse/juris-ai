import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  authenticatedBackendFetch,
  bffError,
  clearSessionCookies,
  extractTokenPayload,
  fetchBackend,
  readBackendPayload,
  REFRESH_TOKEN_COOKIE,
  relayBackendResponse,
  serviceUnavailable,
  setSessionCookies,
  type TokenPayload,
} from "@/lib/server/auth";
import { userIdFromAccessToken } from "@/lib/server/jwt";

export const dynamic = "force-dynamic";

async function refreshTokens(refreshToken: string): Promise<TokenPayload | null> {
  const response = await fetchBackend("/auth/access-token", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    return null;
  }
  return extractTokenPayload(await readBackendPayload(response));
}

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  let accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return bffError(401, "UNAUTHORIZED", "Please sign in to continue.");
  }

  try {
    let issued: TokenPayload | undefined;
    if (!accessToken && refreshToken) {
      const tokens = await refreshTokens(refreshToken);
      if (!tokens) {
        const response = bffError(401, "UNAUTHORIZED", "Please sign in to continue.");
        clearSessionCookies(response);
        return response;
      }
      issued = tokens;
      accessToken = tokens.access_token;
    }

    const userId = accessToken ? userIdFromAccessToken(accessToken) : null;
    if (!userId) {
      const response = bffError(401, "UNAUTHORIZED", "Please sign in to continue.");
      clearSessionCookies(response);
      return response;
    }

    const result = await authenticatedBackendFetch({
      path: `/users/${encodeURIComponent(userId)}`,
      accessToken,
      refreshToken,
      init: { method: "GET", headers: { Accept: "application/json" } },
    });
    const response = await relayBackendResponse(result.response);
    const cookiesToSet = result.refreshedTokens ?? issued;
    if (cookiesToSet) {
      setSessionCookies(response, cookiesToSet);
    }
    if (result.clearSession) {
      clearSessionCookies(response);
    }
    return response;
  } catch {
    return serviceUnavailable();
  }
}
