"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { sendChat, type SendChatInput } from "@/lib/api/chat";
import {
  chatStreamingEnabled,
  sendChatStream,
  type ChatStreamProgress,
} from "@/lib/api/chat-stream";
import { isAbortError } from "@/lib/api/sse";
import { conversationKeys } from "@/features/conversations/queries";
import type {
  ChatResponse,
  ChatStreamComplete,
  ConversationAnswerCache,
  ConversationApprovalCache,
} from "@/lib/api/types";

export type SendMessageInput = Omit<SendChatInput, "conversationId">;

export type SendMessageResult =
  | { kind: "stream"; complete: ChatStreamComplete }
  | { kind: "sync"; response: ChatResponse }
  | { kind: "cancelled" };

export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  const controllerRef = useRef<AbortController | null>(null);
  const [streamProgress, setStreamProgress] =
    useState<ChatStreamProgress | null>(null);
  const [streamActive, setStreamActive] = useState(false);
  const streaming = chatStreamingEnabled();

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [conversationId],
  );

  const mutation = useMutation({
    mutationFn: async (input: SendMessageInput): Promise<SendMessageResult> => {
      if (!streaming) {
        return {
          kind: "sync",
          response: await sendChat({ ...input, conversationId }),
        };
      }

      const controller = new AbortController();
      controllerRef.current = controller;
      setStreamActive(true);
      try {
        return {
          kind: "stream",
          complete: await sendChatStream(
            { ...input, conversationId },
            {
              signal: controller.signal,
              onProgress: setStreamProgress,
            },
          ),
        };
      } catch (error) {
        if (isAbortError(error) || controller.signal.aborted) {
          return { kind: "cancelled" };
        }
        throw error;
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
        setStreamActive(false);
      }
    },
    onMutate: () => {
      setStreamProgress(
        streaming
          ? { status: "connecting", draftContent: "" }
          : null,
      );
    },
    onSuccess: (result) => {
      if (result.kind === "cancelled") {
        void queryClient.invalidateQueries({
          queryKey: conversationKeys.history(conversationId),
        });
        return;
      }

      const assistantEventId =
        result.kind === "stream"
          ? result.complete.metadata.assistant_event_id
          : result.response.assistant_event.id;
      const details =
        result.kind === "stream"
          ? {
              citations: result.complete.metadata.citations,
              sources: result.complete.metadata.sources,
              usage: result.complete.metadata.usage,
            }
          : {
              citations: result.response.response.citations,
              sources: result.response.response.sources,
              usage: result.response.response.usage,
            };
      queryClient.setQueryData<ConversationAnswerCache>(
        conversationKeys.answers(conversationId),
        (current = {}) => ({
          ...current,
          [assistantEventId]: details,
        }),
      );

      if (result.kind === "stream") {
        const approval =
          result.complete.metadata.approval ??
          result.complete.metadata.response_metadata.approval;
        if (approval) {
          queryClient.setQueryData<ConversationApprovalCache>(
            conversationKeys.approvals(conversationId),
            (current = {}) => ({
              ...current,
              [approval.approval_id]: approval,
            }),
          );
        }
      }

      void Promise.all([
        queryClient.invalidateQueries({
          queryKey: conversationKeys.history(conversationId),
        }),
        queryClient.invalidateQueries({
          queryKey: conversationKeys.detail(conversationId),
        }),
        queryClient.invalidateQueries({ queryKey: conversationKeys.list() }),
      ]);
    },
  });

  return {
    ...mutation,
    streaming,
    streamProgress,
    streamActive,
    stop: () => controllerRef.current?.abort(),
  };
}
