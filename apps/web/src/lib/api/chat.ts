import { apiFetch } from "@/lib/api/client";
import { normalizeConversationEvent } from "@/lib/api/conversations";
import type { ChatResponse } from "@/lib/api/types";

export interface SendChatInput {
  conversationId: string;
  message: string;
  files: File[];
}

export function buildChatFormData(input: SendChatInput): FormData {
  const form = new FormData();
  form.append("conversation_id", input.conversationId);
  form.append("message", input.message);

  for (const file of input.files) {
    form.append("files", file);
  }

  return form;
}

export async function sendChat(input: SendChatInput): Promise<ChatResponse> {
  const response = await apiFetch<ChatResponse>("/api/backend/chat", {
    method: "POST",
    body: buildChatFormData(input),
  });

  return {
    ...response,
    user_event: normalizeConversationEvent(response.user_event),
    assistant_event: normalizeConversationEvent(response.assistant_event),
  };
}
