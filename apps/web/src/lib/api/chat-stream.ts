import { z } from "zod";

import { buildChatFormData, type SendChatInput } from "@/lib/api/chat";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api/client";
import { ApiError, normalizeApiError } from "@/lib/api/errors";
import {
  isAbortError,
  parseSseJson,
  parseSseStream,
} from "@/lib/api/sse";
import type {
  ChatStreamComplete,
  ChatStreamMessage,
} from "@/lib/api/types";

const citationSchema = z.object({
  title: z.string(),
  source: z.string(),
  reference: z.string().nullish(),
  page: z.number().nullish(),
  snippet: z.string().nullish(),
});

const sourceSchema = z.object({
  title: z.string(),
  uri: z.string().nullish(),
  type: z.string().nullish(),
});

const usageSchema = z.object({
  provider: z.string().nullish(),
  model: z.string().nullish(),
  prompt_tokens: z.number(),
  completion_tokens: z.number(),
  total_tokens: z.number(),
  latency_ms: z.number().nullish(),
});

const approvalSchema = z
  .object({
    approval_id: z.string(),
    status: z.enum(["waiting", "approved", "rejected", "edited", "expired"]),
    expires_at: z.string().optional(),
    agent_action_id: z.string().optional(),
    requested_by: z.string().optional(),
    created_at: z.string().optional(),
  })
  .passthrough();

const responseMetadataSchema = z
  .object({
    agents: z.array(z.string()).default([]),
    workflow: z.string().nullish(),
    approval: approvalSchema.nullish(),
  })
  .passthrough();

const messageSchema = z.object({
  content: z.string(),
  is_final: z.literal(false),
  metadata: z
    .object({
      status: z.string(),
      phase: z.string().optional(),
    })
    .passthrough(),
});

const completeSchema = z.object({
  content: z.string(),
  is_final: z.literal(true),
  metadata: z
    .object({
      status: z.literal("complete"),
      citations: z.array(citationSchema).default([]),
      sources: z.array(sourceSchema).default([]),
      usage: usageSchema,
      response_metadata: responseMetadataSchema,
      approval: approvalSchema.nullish(),
      conversation_id: z.string().min(1),
      user_event_id: z.string().min(1),
      assistant_event_id: z.string().min(1),
    })
    .passthrough(),
});

export interface ChatStreamProgress {
  status: string;
  phase?: string;
  draftContent: string;
}

export interface SendChatStreamOptions {
  signal?: AbortSignal;
  onProgress?: (
    progress: ChatStreamProgress,
    event: ChatStreamMessage,
  ) => void;
}

export function chatStreamingEnabled(
  configured = process.env.NEXT_PUBLIC_CHAT_STREAMING,
): boolean {
  return configured?.trim().toLowerCase() !== "false";
}

export function accumulateStreamContent(
  current: string,
  incoming: string,
): string {
  if (!incoming) return current;
  if (!current || incoming.startsWith(current)) return incoming;
  if (current.endsWith(incoming)) return current;
  return `${current}${incoming}`;
}

function streamProtocolError(message: string, requestId?: string): ApiError {
  return new ApiError({
    code: "STREAM_PROTOCOL_ERROR",
    message,
    httpStatus: 502,
    requestId,
  });
}

async function readPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function validateEvent<T>(
  schema: z.ZodType<T>,
  value: unknown,
  eventName: string,
  requestId?: string,
): T {
  const result = schema.safeParse(value);
  if (result.success) return result.data;
  throw streamProtocolError(
    `Juris AI returned an invalid ${eventName} stream event.`,
    requestId,
  );
}

export async function sendChatStream(
  input: SendChatInput,
  options: SendChatStreamOptions = {},
): Promise<ChatStreamComplete> {
  let response: Response;
  try {
    response = await fetch("/api/backend/chat/stream", {
      method: "POST",
      body: buildChatFormData(input),
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "text/event-stream" },
      signal: options.signal,
    });
  } catch (error) {
    if (isAbortError(error) || options.signal?.aborted) throw error;
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "Could not reach Juris AI. Check your connection and try again.",
      httpStatus: 0,
    });
  }

  const requestId = response.headers.get("x-request-id") ?? undefined;
  if (!response.ok) {
    const payload = await readPayload(response);
    if (
      response.status === 401 &&
      typeof window !== "undefined"
    ) {
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }
    throw new ApiError(
      normalizeApiError(
        payload,
        response.status,
        requestId,
        response.headers.get("retry-after"),
      ),
    );
  }

  if (
    !response.headers
      .get("content-type")
      ?.toLowerCase()
      .startsWith("text/event-stream") ||
    !response.body
  ) {
    throw streamProtocolError(
      "Juris AI did not return a readable event stream.",
      requestId,
    );
  }

  let draftContent = "";
  for await (const event of parseSseStream(response.body, options.signal)) {
    if (!["message", "complete", "error"].includes(event.event)) {
      continue;
    }
    const payload = parseSseJson<unknown>(event, requestId);

    if (event.event === "message") {
      const message = validateEvent(
        messageSchema,
        payload,
        "message",
        requestId,
      ) as ChatStreamMessage;
      draftContent = accumulateStreamContent(draftContent, message.content);
      options.onProgress?.(
        {
          status: message.metadata.status,
          phase: message.metadata.phase,
          draftContent,
        },
        message,
      );
      continue;
    }

    if (event.event === "complete") {
      const complete = validateEvent(
        completeSchema,
        payload,
        "complete",
        requestId,
      ) as ChatStreamComplete;
      if (complete.metadata.conversation_id !== input.conversationId) {
        throw streamProtocolError(
          "Juris AI completed a different conversation than requested.",
          requestId,
        );
      }
      return complete;
    }

    if (event.event === "error") {
      throw new ApiError(normalizeApiError(payload, 500, requestId));
    }
  }

  throw streamProtocolError(
    "The Juris AI stream ended before a complete event.",
    requestId,
  );
}
