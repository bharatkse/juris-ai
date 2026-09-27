import { ApiError, normalizeApiError } from "@/lib/api/errors";

export const AUTH_UNAUTHORIZED_EVENT = "juris:unauthorized";

type Envelope<T> = {
  success: boolean;
  data?: T;
  error?: unknown;
};

function isEnvelope<T>(value: unknown): value is Envelope<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "success" in value &&
    typeof (value as Envelope<T>).success === "boolean"
  );
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  const text = await response.text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function apiFetch<T>(
  input: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(input, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "Could not reach Juris AI. Check your connection and try again.",
      httpStatus: 0,
    });
  }

  const payload = await readResponse(response);

  if (!response.ok || (isEnvelope(payload) && !payload.success)) {
    const normalized = normalizeApiError(
      payload,
      response.status,
      response.headers.get("x-request-id"),
      response.headers.get("retry-after"),
    );

    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      (input.startsWith("/api/backend/") || input === "/api/auth/me")
    ) {
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }

    throw new ApiError(normalized);
  }

  if (isEnvelope<T>(payload)) {
    return payload.data as T;
  }

  return payload as T;
}

export function jsonRequest(body: unknown, init: RequestInit = {}): RequestInit {
  return {
    ...init,
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  };
}
