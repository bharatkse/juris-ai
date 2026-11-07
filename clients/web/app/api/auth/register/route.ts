import { NextResponse } from "next/server";

import { registerSchema } from "@/features/auth/schemas";
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

function envelopeData(payload: unknown): unknown {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "data" in payload
  ) {
    return (payload as Record<string, unknown>).data;
  }

  return payload;
}

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

  const parsed = registerSchema.safeParse(body);
  if (!parsed.success) {
    return validationError(parsed.error);
  }

  const registration = {
    ...parsed.data,
    first_name: parsed.data.first_name || undefined,
    last_name: parsed.data.last_name || undefined,
  };

  let user: unknown;
  try {
    const upstream = await fetchBackend("/users", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(registration),
    });

    if (!upstream.ok) {
      return relayBackendResponse(upstream);
    }

    user = envelopeData(await readBackendPayload(upstream));
  } catch {
    return serviceUnavailable();
  }

  let tokens = null;
  try {
    const form = new URLSearchParams({
      username: parsed.data.email,
      password: parsed.data.password,
    });
    const login = await fetchBackend("/auth/login", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form,
    });

    if (login.ok) {
      tokens = extractTokenPayload(await readBackendPayload(login));
    }
  } catch {
    // Registration succeeded. The client can send the user to sign in.
  }

  const response = NextResponse.json(
    {
      success: true,
      data: { authenticated: Boolean(tokens), user },
      metadata: {},
    },
    { status: 201, headers: { "Cache-Control": "no-store" } },
  );

  if (tokens) {
    setSessionCookies(response, tokens);
  }

  return response;
}
