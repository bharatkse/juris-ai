import { describe, expect, it } from "vitest";

import { isSameOriginRequest, relayBackendResponse } from "@/lib/server/auth";

describe("isSameOriginRequest", () => {
  it("allows missing Origin for non-browser clients", () => {
    expect(
      isSameOriginRequest(new Request("http://127.0.0.1:3100/api/auth/login")),
    ).toBe(true);
  });

  it("treats localhost and 127.0.0.1 as the same loopback origin", () => {
    expect(
      isSameOriginRequest(
        new Request("http://127.0.0.1:3100/api/auth/login", {
          headers: { origin: "http://localhost:3100" },
        }),
      ),
    ).toBe(true);
    expect(
      isSameOriginRequest(
        new Request("http://localhost:3100/api/auth/register", {
          headers: {
            origin: "http://127.0.0.1:3100",
            host: "localhost:3100",
          },
        }),
      ),
    ).toBe(true);
  });

  it("rejects a different site", () => {
    expect(
      isSameOriginRequest(
        new Request("http://127.0.0.1:3100/api/auth/login", {
          headers: { origin: "https://attacker.example" },
        }),
      ),
    ).toBe(false);
  });
});

describe("relayBackendResponse", () => {
  it("relays SSE as a live stream with anti-buffering headers", async () => {
    const encoder = new TextEncoder();
    let source!: ReadableStreamDefaultController<Uint8Array>;
    const upstream = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          source = controller;
          controller.enqueue(encoder.encode("event: message\n"));
        },
      }),
      {
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          connection: "keep-alive",
          "x-accel-buffering": "no",
          "x-request-id": "req-relay",
        },
      },
    );

    const relayed = await relayBackendResponse(upstream);
    expect(relayed.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(relayed.headers.get("connection")).toBe("keep-alive");
    expect(relayed.headers.get("x-accel-buffering")).toBe("no");
    expect(relayed.headers.get("x-request-id")).toBe("req-relay");

    const reader = relayed.body!.getReader();
    const first = await reader.read();
    expect(new TextDecoder().decode(first.value)).toBe("event: message\n");
    source.enqueue(encoder.encode("data: {}\n\n"));
    source.close();
    const second = await reader.read();
    expect(new TextDecoder().decode(second.value)).toBe("data: {}\n\n");
  });

  it("keeps existing buffered JSON behavior", async () => {
    const relayed = await relayBackendResponse(
      new Response('{"ok":true}', {
        headers: { "content-type": "application/json" },
      }),
    );
    expect(relayed.headers.get("cache-control")).toBe("no-store");
    await expect(relayed.text()).resolves.toBe('{"ok":true}');
  });
});
