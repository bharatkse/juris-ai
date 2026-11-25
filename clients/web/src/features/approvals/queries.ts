"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  decideApproval,
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
  };
}

export function useApprovalDecision(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ApprovalDecisionInput) => decideApproval(input),
    onSuccess: (response) => {
      const metadata = approvalMetadata(response);
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
