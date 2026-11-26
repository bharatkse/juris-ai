import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, GET_RETRY_ATTEMPTS } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("apiFetch", () => {
  it("unwraps ApiResponse envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ success: true, data: { id: "1" } }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await expect(apiFetch<{ id: string }>("/api/backend/x")).resolves.toEqual({
      id: "1",
    });
  });

  it("retries idempotent GET on 502 then succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("bad", { status: 502 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, data: { ok: true } }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/backend/health")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("bad", { status: 502 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiFetch("/api/backend/chat", { method: "POST" }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("normalizes error code and request id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            error: { code: "FORBIDDEN", message: "No" },
          }),
          {
            status: 403,
            headers: {
              "content-type": "application/json",
              "x-request-id": "req_1",
            },
          },
        ),
      ),
    );

    try {
      await apiFetch("/api/backend/x");
      throw new Error("expected failure");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.code).toBe("FORBIDDEN");
      expect(apiError.requestId).toBe("req_1");
      expect(apiError.httpStatus).toBe(403);
    }
  });

  it("aborts without retrying remaining GET attempts", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn().mockImplementation(() => {
      const error = new Error("Aborted");
      error.name = "AbortError";
      return Promise.reject(error);
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiFetch("/api/backend/x", { signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(GET_RETRY_ATTEMPTS).toBe(3);
  });
});
