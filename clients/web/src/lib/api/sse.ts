import { ApiError } from "@/lib/api/errors";

export interface ServerSentEvent {
  event: string;
  data: string;
  id?: string;
}

interface EventBlock {
  event: string;
  data: string[];
  id?: string;
}

function emptyBlock(): EventBlock {
  return { event: "message", data: [] };
}

function takeLine(
  buffer: string,
  final: boolean,
): { line: string; rest: string } | null {
  for (let index = 0; index < buffer.length; index += 1) {
    const character = buffer[index];
    if (character === "\n") {
      return {
        line: buffer.slice(0, index),
        rest: buffer.slice(index + 1),
      };
    }
    if (character === "\r") {
      if (index + 1 === buffer.length && !final) return null;
      const width = buffer[index + 1] === "\n" ? 2 : 1;
      return {
        line: buffer.slice(0, index),
        rest: buffer.slice(index + width),
      };
    }
  }

  return final && buffer ? { line: buffer, rest: "" } : null;
}

function applyLine(block: EventBlock, line: string): void {
  if (!line || line.startsWith(":")) return;
  const separator = line.indexOf(":");
  const field = separator < 0 ? line : line.slice(0, separator);
  let value = separator < 0 ? "" : line.slice(separator + 1);
  if (value.startsWith(" ")) value = value.slice(1);

  if (field === "event") {
    block.event = value || "message";
  } else if (field === "data") {
    block.data.push(value);
  } else if (field === "id" && !value.includes("\0")) {
    block.id = value;
  }
}

function dispatchBlock(block: EventBlock): ServerSentEvent | null {
  if (!block.data.length) return null;
  return {
    event: block.event || "message",
    data: block.data.join("\n"),
    ...(block.id !== undefined ? { id: block.id } : {}),
  };
}

function cancellationError(): Error {
  if (typeof DOMException !== "undefined") {
    return new DOMException("The stream was stopped.", "AbortError");
  }
  const error = new Error("The stream was stopped.");
  error.name = "AbortError";
  return error;
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof Error && error.name === "AbortError") ||
    (typeof DOMException !== "undefined" &&
      error instanceof DOMException &&
      error.name === "AbortError")
  );
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ServerSentEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let block = emptyBlock();
  let finished = false;

  const abort = () => {
    void reader.cancel(signal?.reason).catch(() => undefined);
  };
  signal?.addEventListener("abort", abort, { once: true });

  try {
    while (true) {
      if (signal?.aborted) throw cancellationError();
      const result = await reader.read();
      if (signal?.aborted) throw cancellationError();
      if (result.done) {
        finished = true;
        buffer += decoder.decode();
      } else {
        buffer += decoder.decode(result.value, { stream: true });
      }

      while (true) {
        const extracted = takeLine(buffer, finished);
        if (!extracted) break;
        buffer = extracted.rest;
        if (extracted.line === "") {
          const event = dispatchBlock(block);
          block = emptyBlock();
          if (event) yield event;
        } else {
          applyLine(block, extracted.line);
        }
      }

      if (finished) {
        const event = dispatchBlock(block);
        if (event) yield event;
        break;
      }
    }
  } finally {
    signal?.removeEventListener("abort", abort);
    if (!finished) {
      await reader.cancel().catch(() => undefined);
    }
    reader.releaseLock();
  }
}

export function parseSseJson<T>(
  event: ServerSentEvent,
  requestId?: string,
): T {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    throw new ApiError({
      code: "STREAM_MALFORMED_EVENT",
      message: `Juris AI returned malformed ${event.event} stream data.`,
      httpStatus: 502,
      requestId,
    });
  }
}
