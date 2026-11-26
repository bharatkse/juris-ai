import { apiFetch, jsonRequest } from "@/lib/api/client";
import type {
  Citation,
  Conversation,
  ConversationEvent,
  ConversationEventMetadata,
  Paginated,
  Source,
} from "@/types/api";

const CONVERSATIONS_ENDPOINT = "/api/backend/conversations";

export function buildConversationListUrl(offset = 0, limit = 20): string {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  return `${CONVERSATIONS_ENDPOINT}?${params.toString()}`;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  parent_event_id: string | null;
  role: ConversationEvent["role"];
  content: string;
  metadata?: ConversationEventMetadata;
  event_metadata?: ConversationEventMetadata;
  citations?: Citation[];
  sources?: Source[];
  created_at: string;
}

export function normalizeConversationEvent(
  event: ConversationMessage | ConversationEvent,
): ConversationEvent {
  const metadata: ConversationEventMetadata = {
    ...(event.event_metadata ?? {}),
    ...("metadata" in event && event.metadata ? event.metadata : {}),
  };
  const message = event as ConversationMessage;
  if (message.citations?.length) {
    metadata.citations = message.citations;
  }
  if (message.sources?.length) {
    metadata.sources = message.sources;
  }

  return {
    id: event.id,
    conversation_id: event.conversation_id,
    parent_event_id: event.parent_event_id,
    role: event.role,
    content: event.content,
    metadata,
    created_at: event.created_at,
  };
}

export async function listConversations(
  offset = 0,
  limit = 20,
  signal?: AbortSignal,
): Promise<Paginated<Conversation>> {
  return apiFetch<Paginated<Conversation>>(
    buildConversationListUrl(offset, limit),
    { signal },
  );
}

export async function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>(
    CONVERSATIONS_ENDPOINT,
    jsonRequest(title ? { title } : {}, { method: "POST" }),
  );
}

export async function getConversation(
  id: string,
  signal?: AbortSignal,
): Promise<Conversation> {
  return apiFetch<Conversation>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}`,
    { signal },
  );
}

export async function setConversationMemoryDisabled(
  id: string,
  memoryDisabled: boolean,
): Promise<Conversation> {
  return apiFetch<Conversation>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}/memory`,
    jsonRequest({ memory_disabled: memoryDisabled }, { method: "PUT" }),
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
  signal?: AbortSignal,
): Promise<Paginated<ConversationEvent>> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const page = await apiFetch<Paginated<ConversationMessage>>(
    `${CONVERSATIONS_ENDPOINT}/${encodeURIComponent(id)}/messages?${params.toString()}`,
    { signal },
  );

  return {
    ...page,
    items: page.items.map(normalizeConversationEvent),
  };
}
