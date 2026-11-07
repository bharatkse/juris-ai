import type { NormalizedApiError } from "@/lib/api/errors";

export interface ChatErrorPresentation {
  kind: "rate" | "token" | "general";
  title: string;
  message: string;
  retryable: boolean;
  retryAfterSeconds?: number;
}

export function getChatErrorPresentation(
  error: NormalizedApiError,
): ChatErrorPresentation {
  if (error.code === "RATE_LIMIT_EXCEEDED") {
    return {
      kind: "rate",
      title: "Request limit reached",
      message: "Too many requests this minute. Wait and try again.",
      retryable: true,
      retryAfterSeconds: error.retryAfterSeconds,
    };
  }

  if (error.code === "TOKEN_QUOTA_EXCEEDED") {
    return {
      kind: "token",
      title: "Daily usage limit reached",
      message: "Daily token quota reached. Try again tomorrow.",
      retryable: false,
    };
  }

  return {
    kind: "general",
    title: "Juris AI could not complete this request",
    message: error.message,
    retryable: true,
  };
}

export function remainingRetrySeconds(
  retryAfterSeconds: number | undefined,
  elapsedSeconds: number,
): number {
  if (retryAfterSeconds === undefined) return 0;
  return Math.max(0, retryAfterSeconds - elapsedSeconds);
}
