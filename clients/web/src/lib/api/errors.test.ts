import { describe, expect, it } from "vitest";

import { normalizeApiError, parseRetryAfter } from "@/lib/api/errors";

describe("normalizeApiError", () => {
  it("normalizes the Juris API error envelope", () => {
    expect(
      normalizeApiError(
        {
          success: false,
          error: {
            code: "USER_ALREADY_EXISTS",
            message: "An account with this email already exists.",
          },
          metadata: { request_id: "req-123" },
        },
        409,
      ),
    ).toEqual({
      code: "USER_ALREADY_EXISTS",
      message: "An account with this email already exists.",
      httpStatus: 409,
      requestId: "req-123",
    });
  });

  it("normalizes a FastAPI detail message", () => {
    expect(normalizeApiError({ detail: "Invalid credentials" }, 401)).toMatchObject(
      {
        code: "UNAUTHORIZED",
        message: "Invalid credentials",
        httpStatus: 401,
      },
    );
  });

  it("collects FastAPI validation issues by field", () => {
    const error = normalizeApiError(
      {
        detail: [
          {
            loc: ["body", "email"],
            msg: "value is not a valid email address",
            type: "value_error",
          },
          {
            loc: ["body", "password"],
            msg: "String should have at least 8 characters",
            type: "string_too_short",
          },
        ],
      },
      422,
      "req-header",
    );

    expect(error.fields).toEqual({
      email: ["value is not a valid email address"],
      password: ["String should have at least 8 characters"],
    });
    expect(error.requestId).toBe("req-header");
  });

  it("falls back without exposing unknown response data", () => {
    expect(normalizeApiError("<html>bad gateway</html>", 502)).toEqual({
      code: "INTERNAL_SERVER_ERROR",
      message: "The legal service is temporarily unavailable.",
      httpStatus: 502,
      requestId: undefined,
    });
  });

  it("normalizes Retry-After seconds and dates", () => {
    expect(
      normalizeApiError(
        { error: { code: "RATE_LIMIT_EXCEEDED", message: "Slow down" } },
        429,
        null,
        "12",
      ).retryAfterSeconds,
    ).toBe(12);
    expect(
      parseRetryAfter(
        "Tue, 15 Sep 2026 10:00:10 GMT",
        new Date("2026-09-15T10:00:00Z").getTime(),
      ),
    ).toBe(10);
  });
});
