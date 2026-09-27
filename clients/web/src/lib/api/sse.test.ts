import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";
import {
  parseSseJson,
  parseSseStream,
  type ServerSentEvent,
} from "@/lib/api/sse";

function byteStream(chunks: Uint8Array[], close = true) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      if (close) controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events: ServerSentEvent[] = [];
  for await (const event of parseSseStream(stream)) events.push(event);
  return events;
}

describe("parseSseStream", () => {
  it("handles arbitrary UTF-8 byte boundaries, CRLF, and multi-line data", async () => {
    const encoded = new TextEncoder().encode(
      [
        ": heartbeat\r\n",
        "id: evt-1\r\n",
        "event: message\r\n",
        "data: {\"content\":\"A😀\",\r\n",
        "data: \"is_final\":false}\r\n",
        "\r\n",
      ].join(""),
    );
    const chunks = Array.from(encoded, (byte) => new Uint8Array([byte]));

    await expect(collect(byteStream(chunks))).resolves.toEqual([
      {
        event: "message",
        id: "evt-1",
        data: '{"content":"A😀",\n"is_final":false}',
      },
    ]);
  });

  it("dispatches a final trailing block without a blank line", async () => {
    const bytes = new TextEncoder().encode(
      'event: complete\ndata: {"is_final":true}',
    );
    await expect(collect(byteStream([bytes]))).resolves.toEqual([
      {
        event: "complete",
        data: '{"is_final":true}',
      },
    ]);
  });

  it("cancels a pending reader with AbortSignal", async () => {
    const encoder = new TextEncoder();
    const stream = byteStream(
      [encoder.encode("event: message\ndata: {}\n\n")],
      false,
    );
    const controller = new AbortController();
    const iterator = parseSseStream(stream, controller.signal);

    await expect(iterator.next()).resolves.toMatchObject({ done: false });
    controller.abort();
    await expect(iterator.next()).rejects.toMatchObject({ name: "AbortError" });
  });

  it("normalizes malformed JSON", () => {
    expect(() =>
      parseSseJson({ event: "complete", data: "{not-json" }, "req-stream"),
    ).toThrowError(ApiError);
    try {
      parseSseJson({ event: "complete", data: "{not-json" }, "req-stream");
    } catch (error) {
      expect(error).toMatchObject({
        code: "STREAM_MALFORMED_EVENT",
        requestId: "req-stream",
      });
    }
  });
});
