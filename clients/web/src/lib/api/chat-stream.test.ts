import { afterEach, describe, expect, it, vi } from "vitest";

import {
  accumulateStreamContent,
  chatStreamingEnabled,
  sendChatStream,
} from "@/lib/api/chat-stream";

const complete = {
  content: "Final canonical answer.",
  is_final: true,
  metadata: {
    status: "complete",
    citations: [],
    sources: [],
    usage: {
      prompt_tokens: 10,
      completion_tokens: 20,
      total_tokens: 30,
    },
    response_metadata: { agents: ["legal"], workflow: "research" },
    conversation_id: "conv_1",
    user_event_id: "user_event_1",
    assistant_event_id: "assistant_event_1",
  },
};

function sseResponse(blocks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const block of blocks) controller.enqueue(encoder.encode(block));
        controller.close();
      },
    }),
    {
      headers: {
        "content-type": "text/event-stream; charset=utf-8",
        "x-request-id": "req-stream",
      },
    },
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("sendChatStream", () => {
  it("defaults streaming on and supports an explicit false fallback", () => {
    expect(chatStreamingEnabled(undefined)).toBe(true);
    expect(chatStreamingEnabled("false")).toBe(false);
    expect(chatStreamingEnabled("FALSE")).toBe(false);
  });

  it("accumulates delta and cumulative future chunks safely", () => {
    expect(accumulateStreamContent("", "Hel")).toBe("Hel");
    expect(accumulateStreamContent("Hel", "Hello")).toBe("Hello");
    expect(accumulateStreamContent("Hello", " world")).toBe("Hello world");
    expect(accumulateStreamContent("Hello world", "world")).toBe("Hello world");
  });

  it("reports lifecycle and progressive content before canonical completion", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          `event: message\r\ndata: ${JSON.stringify({
            content: "Hel",
            is_final: false,
            metadata: { status: "working", phase: "planning_and_research" },
          })}\r\n\r\n`,
          `event: message\ndata: ${JSON.stringify({
            content: "Hello",
            is_final: false,
            metadata: { status: "working", phase: "drafting" },
          })}\n\n`,
          `event: message\ndata: ${JSON.stringify({
            content: " world",
            is_final: false,
            metadata: { status: "working", phase: "drafting" },
          })}\n\n`,
          `event: complete\ndata: ${JSON.stringify(complete)}`,
        ]),
      ),
    );
    const drafts: string[] = [];

    const result = await sendChatStream(
      { conversationId: "conv_1", message: "Question", files: [] },
      { onProgress: (progress) => drafts.push(progress.draftContent) },
    );

    expect(drafts).toEqual(["Hel", "Hello", "Hello world"]);
    expect(result.content).toBe("Final canonical answer.");
    expect(result.metadata.assistant_event_id).toBe("assistant_event_1");
  });

  it("normalizes HTTP error envelopes and Retry-After", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            error: {
              code: "RATE_LIMIT_EXCEEDED",
              message: "Slow down.",
            },
          }),
          {
            status: 429,
            headers: {
              "content-type": "application/json",
              "retry-after": "9",
            },
          },
        ),
      ),
    );

    await expect(
      sendChatStream({
        conversationId: "conv_1",
        message: "Question",
        files: [],
      }),
    ).rejects.toMatchObject({
      code: "RATE_LIMIT_EXCEEDED",
      retryAfterSeconds: 9,
    });
  });

  it("aborts neutrally distinguishable from protocol failures", async () => {
    const encoder = new TextEncoder();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  `event: message\ndata: ${JSON.stringify({
                    content: "",
                    is_final: false,
                    metadata: { status: "working", phase: "planning" },
                  })}\n\n`,
                ),
              );
            },
          }),
          { headers: { "content-type": "text/event-stream" } },
        ),
      ),
    );
    const controller = new AbortController();

    await expect(
      sendChatStream(
        { conversationId: "conv_1", message: "Question", files: [] },
        {
          signal: controller.signal,
          onProgress: () => controller.abort(),
        },
      ),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("surfaces SSE error events instead of a protocol hang", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          `event: error\ndata: ${JSON.stringify({
            success: false,
            error: {
              code: "CLIENT_CONNECTION_ERROR",
              message:
                "Cannot reach Ollama at http://ollama:11434. Start the Ollama service, or set GROQ_API_KEY in .env.",
            },
            metadata: { request_id: "req-stream" },
          })}\n\n`,
        ]),
      ),
    );

    await expect(
      sendChatStream({
        conversationId: "conv_1",
        message: "Question",
        files: [],
      }),
    ).rejects.toMatchObject({
      code: "CLIENT_CONNECTION_ERROR",
      message:
        "Cannot reach Ollama at http://ollama:11434. Start the Ollama service, or set GROQ_API_KEY in .env.",
    });
  });
});
