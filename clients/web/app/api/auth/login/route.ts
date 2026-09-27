import { NextResponse } from "next/server";

import { loginSchema } from "@/features/auth/schemas";
import {
  bffError,
  extractTokenPayload,
  fetchBackend,
  isSameOriginRequest,
  readBackendPayload,
  relayBackendResponse,
  serviceUnavailable,
  setSessionCookies,
  validationError,
} from "@/lib/server/auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  if (!isSameOriginRequest(request)) {
    return bffError(403, "FORBIDDEN", "Cross-origin requests are not allowed.");
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return bffError(400, "BAD_REQUEST", "A valid JSON body is required.");
  }

  const parsed = loginSchema.safeParse(body);
  if (!parsed.success) {
    return validationError(parsed.error);
  }

  const form = new URLSearchParams({
    username: parsed.data.email,
    password: parsed.data.password,
  });

  try {
    const upstream = await fetchBackend("/auth/login", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form,
    });

    if (!upstream.ok) {
      return relayBackendResponse(upstream);
    }

    const tokens = extractTokenPayload(await readBackendPayload(upstream));
    if (!tokens) {
      return bffError(
        502,
        "INVALID_AUTH_RESPONSE",
        "The authentication service returned an invalid response.",
      );
    }

    const response = NextResponse.json(
      { success: true, data: { authenticated: true }, metadata: {} },
      { headers: { "Cache-Control": "no-store" } },
    );
    setSessionCookies(response, tokens);
    return response;
  } catch {
    return serviceUnavailable();
  }
}
