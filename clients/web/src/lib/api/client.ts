import { ApiError, normalizeApiError } from "@/lib/api/errors";

export const AUTH_UNAUTHORIZED_EVENT = "juris:unauthorized";

/** Default timeout for JSON API calls. Chat streams pass their own signal. */
export const API_TIMEOUT_MS = 30_000;
export const GET_RETRY_ATTEMPTS = 3;
export const GET_RETRY_BASE_MS = 200;

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

function requestMethod(init: RequestInit): string {
  return (init.method ?? "GET").toUpperCase();
}

function isIdempotentGet(method: string): boolean {
  return method === "GET" || method === "HEAD";
}

function isRetryableStatus(status: number): boolean {
  return status === 502 || status === 503 || status === 504;
}

export async function wait(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => resolve(), ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(
        signal?.reason instanceof Error
          ? signal.reason
          : new DOMException("Aborted", "AbortError"),
      );
    };
    if (signal?.aborted) {
      onAbort();
      return;
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export type ApiFetchInit = RequestInit & {
  timeoutMs?: number;
};

export async function apiFetch<T>(
  input: string,
  init: ApiFetchInit = {},
): Promise<T> {
  const { timeoutMs = API_TIMEOUT_MS, signal, ...rest } = init;
  const method = requestMethod(rest);
  const retry = isIdempotentGet(method);
  const attempts = retry ? GET_RETRY_ATTEMPTS : 1;
  let response: Response | undefined;
  let lastNetworkError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
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
      lastNetworkError = undefined;
      if (
        retry &&
        attempt < attempts &&
        isRetryableStatus(response.status)
      ) {
        await wait(GET_RETRY_BASE_MS * 2 ** (attempt - 1), signal ?? undefined);
        continue;
      }
      break;
    } catch (error) {
      lastNetworkError = error;
      if (error instanceof Error && error.name === "AbortError") {
        throw error;
      }
      if (error instanceof Error && error.name === "TimeoutError") {
        if (!retry || attempt === attempts) {
          throw new ApiError({
            code: "NETWORK_TIMEOUT",
            message: "The request took too long. Please try again.",
            httpStatus: 0,
          });
        }
      } else if (!retry || attempt === attempts) {
        throw new ApiError({
          code: "NETWORK_ERROR",
          message:
            "Could not reach Juris AI. Check your connection and try again.",
          httpStatus: 0,
        });
      }
      await wait(GET_RETRY_BASE_MS * 2 ** (attempt - 1), signal ?? undefined);
    }
  }

  if (!response) {
    if (lastNetworkError instanceof Error && lastNetworkError.name === "TimeoutError") {
      throw new ApiError({
        code: "NETWORK_TIMEOUT",
        message: "The request took too long. Please try again.",
        httpStatus: 0,
      });
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
