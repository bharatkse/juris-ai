import type { ZodError } from "zod";
import { z } from "zod";
import { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "juris_access_token";
export const REFRESH_TOKEN_COOKIE = "juris_refresh_token";

const DEFAULT_BACKEND_API_URL = "http://127.0.0.1:8001/api/v1";
const DEFAULT_ACCESS_MAX_AGE = 60 * 60;
const DEFAULT_REFRESH_MAX_AGE = 7 * 24 * 60 * 60;
const DEFAULT_BACKEND_TIMEOUT_MS = 15_000;

const tokenPayloadSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string().optional(),
  expires_in: z.coerce.number().positive().optional(),
  refresh_token: z.string().min(1).nullish(),
  refresh_expires_in: z.coerce.number().positive().nullish(),
});

export type TokenPayload = z.infer<typeof tokenPayloadSchema>;

export interface AuthenticatedBackendResult {
  response: Response;
  refreshedTokens?: TokenPayload;
  clearSession: boolean;
}

function backendApiUrl(path: string): string {
  const configured =
    process.env.BACKEND_API_URL?.trim() || DEFAULT_BACKEND_API_URL;
  const base = new URL(configured.endsWith("/") ? configured : `${configured}/`);

  if (base.protocol !== "http:" && base.protocol !== "https:") {
    throw new Error("BACKEND_API_URL must use http or https");
  }

  return new URL(path.replace(/^\/+/u, ""), base).toString();
}

function authenticatedHeaders(
  headers: HeadersInit | undefined,
  accessToken?: string,
): Headers {
  const result = new Headers(headers);

  result.delete("authorization");
  result.delete("cookie");
  result.delete("host");

  if (accessToken) {
    result.set("Authorization", `Bearer ${accessToken}`);
  }

  return result;
}

export async function fetchBackend(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
  timeoutMs = DEFAULT_BACKEND_TIMEOUT_MS,
): Promise<Response> {
  try {
    return await fetch(backendApiUrl(path), {
      ...init,
      cache: "no-store",
      headers: authenticatedHeaders(init.headers, accessToken),
      redirect: "manual",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError")
    ) {
      throw new Error("BACKEND_TIMEOUT");
    }
    throw error;
  }
}

export async function readBackendPayload(response: Response): Promise<unknown> {
  const text = await response.clone().text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function extractTokenPayload(payload: unknown): TokenPayload | null {
  const root =
    typeof payload === "object" && payload !== null
      ? (payload as Record<string, unknown>)
      : {};
  const candidate =
    typeof root.data === "object" && root.data !== null ? root.data : root;
  const parsed = tokenPayloadSchema.safeParse(candidate);

  return parsed.success ? parsed.data : null;
}

async function refreshAccessToken(
  refreshToken: string,
): Promise<TokenPayload | null> {
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

export async function authenticatedBackendFetch({
  path,
  init,
  accessToken,
  refreshToken,
  timeoutMs,
}: {
  path: string;
  init?: RequestInit;
  accessToken?: string;
  refreshToken?: string;
  timeoutMs?: number;
}): Promise<AuthenticatedBackendResult> {
  let response = await fetchBackend(path, init, accessToken, timeoutMs);

  if (response.status !== 401 || !refreshToken) {
    return {
      response,
      clearSession: response.status === 401 && !refreshToken,
    };
  }

  const refreshedTokens = await refreshAccessToken(refreshToken);
  if (!refreshedTokens) {
    return { response, clearSession: true };
  }

  response = await fetchBackend(
    path,
    init,
    refreshedTokens.access_token,
    timeoutMs,
  );

  return {
    response,
    refreshedTokens,
    clearSession: response.status === 401,
  };
}

const cookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export function setSessionCookies(
  response: NextResponse,
  tokens: TokenPayload,
): void {
  response.cookies.set(ACCESS_TOKEN_COOKIE, tokens.access_token, {
    ...cookieOptions,
    maxAge: Math.floor(tokens.expires_in ?? DEFAULT_ACCESS_MAX_AGE),
  });

  if (tokens.refresh_token) {
    response.cookies.set(REFRESH_TOKEN_COOKIE, tokens.refresh_token, {
      ...cookieOptions,
      maxAge: Math.floor(
        tokens.refresh_expires_in ?? DEFAULT_REFRESH_MAX_AGE,
      ),
    });
  }
}

export function clearSessionCookies(response: NextResponse): void {
  response.cookies.set(ACCESS_TOKEN_COOKIE, "", {
    ...cookieOptions,
    expires: new Date(0),
    maxAge: 0,
  });
  response.cookies.set(REFRESH_TOKEN_COOKIE, "", {
    ...cookieOptions,
    expires: new Date(0),
    maxAge: 0,
  });
}

function defaultPort(protocol: string): string {
  return protocol === "https:" ? "443" : "80";
}

function portOf(url: URL): string {
  return url.port || defaultPort(url.protocol);
}

function canonicalHostname(hostname: string): string {
  const host = hostname.replace(/^\[|\]$/gu, "").toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
    return "loopback";
  }
  return host;
}

function originsMatch(left: URL, right: URL): boolean {
  return (
    left.protocol === right.protocol &&
    portOf(left) === portOf(right) &&
    canonicalHostname(left.hostname) === canonicalHostname(right.hostname)
  );
}

function urlFromHost(hostHeader: string, protocol: string): URL | null {
  try {
    return new URL(`${protocol}//${hostHeader.split(",")[0]!.trim()}`);
  } catch {
    return null;
  }
}

export function isSameOriginRequest(request: Request): boolean {
  const originHeader = request.headers.get("origin");
  if (!originHeader) {
    return true;
  }

  try {
    const origin = new URL(originHeader);
    const requestUrl = new URL(request.url);
    const forwardedProto = request.headers
      .get("x-forwarded-proto")
      ?.split(",")[0]
      ?.trim();
    const protocol = forwardedProto ? `${forwardedProto}:` : origin.protocol;
    const hostHeader =
      request.headers.get("x-forwarded-host") ?? request.headers.get("host");

    const candidates = [
      requestUrl,
      hostHeader ? urlFromHost(hostHeader, protocol) : null,
    ].filter((url): url is URL => url !== null);

    return candidates.some((candidate) => originsMatch(origin, candidate));
  } catch {
    return false;
  }
}

export function bffError(
  status: number,
  code: string,
  message: string,
  fields?: Record<string, string[]>,
): NextResponse {
  return NextResponse.json(
    {
      success: false,
      error: {
        code,
        message,
        ...(fields ? { details: { fields } } : {}),
      },
      metadata: {},
    },
    { status },
  );
}

export function validationError(error: ZodError): NextResponse {
  const fields: Record<string, string[]> = {};

  for (const issue of error.issues) {
    const field = issue.path.join(".") || "form";
    fields[field] = [...(fields[field] ?? []), issue.message];
  }

  return bffError(
    422,
    "VALIDATION_ERROR",
    "Please review the highlighted fields.",
    fields,
  );
}

export function serviceUnavailable(): NextResponse {
  return bffError(
    502,
    "BACKEND_UNAVAILABLE",
    "Juris AI is temporarily unavailable. Please try again.",
  );
}

export async function relayBackendResponse(
  upstream: Response,
): Promise<NextResponse> {
  const streaming = upstream.headers
    .get("content-type")
    ?.toLowerCase()
    .startsWith("text/event-stream");
  const headers = new Headers({
    "Cache-Control": streaming ? "no-cache, no-transform" : "no-store",
  });

  for (const name of [
    "content-type",
    "content-disposition",
    "connection",
    "retry-after",
    "x-accel-buffering",
    "x-request-id",
  ]) {
    const value = upstream.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  if (streaming) {
    if (!headers.has("Connection")) {
      headers.set("Connection", "keep-alive");
    }
    if (!headers.has("X-Accel-Buffering")) {
      headers.set("X-Accel-Buffering", "no");
    }
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers,
    });
  }

  const hasBody = upstream.status !== 204 && upstream.status !== 304;
  const body = hasBody ? await upstream.arrayBuffer() : null;

  return new NextResponse(body, {
    status: upstream.status,
    headers,
  });
}
