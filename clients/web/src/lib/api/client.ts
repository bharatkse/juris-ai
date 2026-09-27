import { ApiError, normalizeApiError } from "@/lib/api/errors";

export const AUTH_UNAUTHORIZED_EVENT = "juris:unauthorized";

/** Default timeout for JSON API calls. Chat streams pass their own signal. */
export const API_TIMEOUT_MS = 30_000;

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

function mergeAbortSignal(
  timeoutMs: number | undefined,
  signal?: AbortSignal | null,
): AbortSignal | undefined {
  const parts: AbortSignal[] = [];
  if (timeoutMs && timeoutMs > 0) {
    parts.push(AbortSignal.timeout(timeoutMs));
  }
  if (signal) {
    parts.push(signal);
  }
  if (parts.length === 0) {
    return undefined;
  }
  if (parts.length === 1) {
    return parts[0];
  }
  return AbortSignal.any(parts);
}

function notifyUnauthorized(input: string, status: number): void {
  if (
    status === 401 &&
    typeof window !== "undefined" &&
    (input.startsWith("/api/backend/") || input === "/api/auth/me")
  ) {
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
  }
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

export type ApiFetchInit = RequestInit & {
  timeoutMs?: number;
};

export async function apiFetch<T>(
  input: string,
  init: ApiFetchInit = {},
): Promise<T> {
  const { timeoutMs = API_TIMEOUT_MS, signal, ...rest } = init;
  let response: Response;

  try {
    response = await fetch(input, {
      ...rest,
      signal: mergeAbortSignal(timeoutMs, signal),
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...rest.headers,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new ApiError({
        code: "NETWORK_TIMEOUT",
        message: "The request took too long. Please try again.",
        httpStatus: 0,
      });
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "Could not reach Juris AI. Check your connection and try again.",
      httpStatus: 0,
    });
  }

  const payload = await readResponse(response);

  if (!response.ok || (isEnvelope(payload) && !payload.success)) {
    notifyUnauthorized(input, response.status);
    throw new ApiError(
      normalizeApiError(
        payload,
        response.status,
        response.headers.get("x-request-id"),
        response.headers.get("retry-after"),
      ),
    );
  }

  if (isEnvelope<T>(payload)) {
    return payload.data as T;
  }

  return payload as T;
}

export async function apiStream(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  try {
    return await fetch(input, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "Could not reach Juris AI. Check your connection and try again.",
      httpStatus: 0,
    });
  }
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
