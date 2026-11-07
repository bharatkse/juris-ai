import { apiFetch, jsonRequest } from "@/lib/api/client";
import type {
  Conversation,
  ConversationEvent,
  ConversationEventMetadata,
  Paginated,
} from "@/lib/api/types";

const CONVERSATIONS_ENDPOINT = "/api/backend/conversations";

export function buildConversationListUrl(offset = 0, limit = 20): string {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  return `${CONVERSATIONS_ENDPOINT}?${params.toString()}`;
}

export function normalizeConversationEvent(
  event: Omit<ConversationEvent, "metadata"> & {
    metadata?: ConversationEventMetadata;
    event_metadata?: ConversationEventMetadata;
  },
): ConversationEvent {
  return {
    ...event,
    metadata: event.metadata ?? event.event_metadata ?? {},
  };
}

export async function listConversations(
  offset = 0,
  limit = 20,
): Promise<Paginated<Conversation>> {
  return apiFetch<Paginated<Conversation>>(
    buildConversationListUrl(offset, limit),
  );
}

export async function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>(
    CONVERSATIONS_ENDPOINT,
    jsonRequest(title ? { title } : {}, { method: "POST" }),
  );
}

export async function getConversation(id: string): Promise<Conversation> {
  return apiFetch<Conversation>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}`,
  );
}

export async function renameConversation(
  id: string,
  title: string,
): Promise<Conversation> {
  return apiFetch<Conversation>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}`,
    jsonRequest({ title }, { method: "PATCH" }),
  );
}

export async function archiveConversation(id: string): Promise<void> {
  return apiFetch<void>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

export async function listConversationEvents(
  id: string,
  offset = 0,
  limit = 100,
): Promise<Paginated<ConversationEvent>> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const page = await apiFetch<
    Paginated<
      Omit<ConversationEvent, "metadata"> & {
        metadata?: ConversationEventMetadata;
        event_metadata?: ConversationEventMetadata;
      }
    >
  >(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}/events?${params.toString()}`,
  );

  return {
    ...page,
    items: page.items.map(normalizeConversationEvent),
  };
}
