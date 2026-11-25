"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  decideApproval,
  retryApprovalResume,
  type ApprovalDecisionInput,
} from "@/features/approvals/api";
import { conversationKeys } from "@/features/conversations/queries";
import { ApiError } from "@/lib/api/errors";
import type {
  ApprovalDecisionResponse,
  ApprovalMetadata,
  ConversationApprovalCache,
} from "@/types/api";

function approvalMetadata(approval: ApprovalDecisionResponse): ApprovalMetadata {
  return {
    approval_id: approval.approval_id,
    agent_action_id: approval.agent_action_id,
    requested_by: approval.requested_by,
    status: approval.status,
    created_at: approval.created_at,
    expires_at: approval.expires_at,
    resume_status: approval.resume_status,
  };
}

function writeApproval(
  queryClient: ReturnType<typeof useQueryClient>,
  conversationId: string,
  metadata: ApprovalMetadata,
) {
  queryClient.setQueryData<ConversationApprovalCache>(
    conversationKeys.approvals(conversationId),
    (current = {}) => ({
      ...current,
      [metadata.approval_id]: metadata,
    }),
  );
  void queryClient.invalidateQueries({
    queryKey: conversationKeys.history(conversationId),
  });
}

export function useApprovalDecision(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ApprovalDecisionInput) => decideApproval(input),
    onSuccess: (response) => {
      writeApproval(queryClient, conversationId, approvalMetadata(response));
    },
    onError: (error, input) => {
      if (
        error instanceof ApiError &&
        (error.code.includes("EXPIRED") || /expired/iu.test(error.message))
      ) {
        queryClient.setQueryData<ConversationApprovalCache>(
          conversationKeys.approvals(conversationId),
          (current = {}) => ({
            ...current,
            [input.approvalId]: {
              ...current[input.approvalId],
              approval_id: input.approvalId,
              status: "expired",
            },
          }),
        );
      }
    },
  });
}

export function useApprovalResume(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      approvalId,
      force,
    }: {
      approvalId: string;
      force?: boolean;
    }) => retryApprovalResume(approvalId, force),
    onSuccess: (response) => {
      writeApproval(queryClient, conversationId, approvalMetadata(response));
    },
  });
}
