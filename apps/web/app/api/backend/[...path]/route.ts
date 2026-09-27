import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  authenticatedBackendFetch,
  bffError,
  clearSessionCookies,
  isSameOriginRequest,
  REFRESH_TOKEN_COOKIE,
  relayBackendResponse,
  serviceUnavailable,
  setSessionCookies,
} from "@/lib/server/auth";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function forwardedHeaders(request: NextRequest): Headers {
  const headers = new Headers();

  for (const name of [
    "accept",
    "content-type",
    "if-match",
    "if-none-match",
  ]) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  return headers;
}

function validPath(segments: string[]): boolean {
  if (!segments.length || segments[0]?.toLowerCase() === "auth") {
    return false;
  }

  return segments.every(
    (segment) =>
      segment.length > 0 &&
      segment !== "." &&
      segment !== ".." &&
      !segment.includes("/") &&
      !segment.includes("\\"),
  );
}

async function proxy(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  if (
    request.method !== "GET" &&
    request.method !== "HEAD" &&
    !isSameOriginRequest(request)
  ) {
    return bffError(403, "FORBIDDEN", "Cross-origin requests are not allowed.");
  }

  const { path: segments } = await context.params;
  if (!validPath(segments)) {
    return bffError(
      404,
      "RESOURCE_NOT_FOUND",
      "That backend route is not available.",
    );
  }

  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return bffError(401, "UNAUTHORIZED", "Please sign in to continue.");
  }

  const bytes =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();
  const body = bytes && bytes.byteLength > 0 ? bytes : undefined;
  const backendPath = `${segments.map(encodeURIComponent).join("/")}${
    request.nextUrl.search
  }`;

  try {
    const result = await authenticatedBackendFetch({
      path: backendPath,
      accessToken,
      refreshToken,
      timeoutMs: segments[0] === "chat" ? 600_000 : undefined,
      init: {
        method: request.method,
        headers: forwardedHeaders(request),
        body,
      },
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

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
