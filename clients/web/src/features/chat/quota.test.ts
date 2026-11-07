import { describe, expect, it } from "vitest";

import {
  getChatErrorPresentation,
  remainingRetrySeconds,
} from "@/features/chat/quota";

describe("quota presentation", () => {
  it("distinguishes minute rate limits and preserves retry delay", () => {
    expect(
      getChatErrorPresentation({
        code: "RATE_LIMIT_EXCEEDED",
        message: "backend copy",
        httpStatus: 429,
        retryAfterSeconds: 15,
      }),
    ).toEqual({
      kind: "rate",
      title: "Request limit reached",
      message: "Too many requests this minute. Wait and try again.",
      retryable: true,
      retryAfterSeconds: 15,
    });
    expect(remainingRetrySeconds(15, 6)).toBe(9);
  });

  it("does not invent a reset time for daily quota", () => {
    const result = getChatErrorPresentation({
      code: "TOKEN_QUOTA_EXCEEDED",
      message: "backend copy",
      httpStatus: 429,
    });
    expect(result.retryable).toBe(false);
    expect(result.message).toBe("Daily token quota reached. Try again tomorrow.");
    expect(result.message).not.toContain("midnight");
  });

  it("keeps general AI failures retryable", () => {
    expect(
      getChatErrorPresentation({
        code: "AI_ERROR",
        message: "The model failed",
        httpStatus: 502,
        requestId: "req-1",
      }),
    ).toMatchObject({
      kind: "general",
      message: "The model failed",
      retryable: true,
    });
  });
});
