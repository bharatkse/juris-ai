import { apiFetch, jsonRequest } from "@/lib/api/client";
import { normalizeConversationEvent } from "@/features/conversations/api";
import type {
  ApprovalDecision,
  ApprovalDecisionResponse,
} from "@/types/api";

export interface ApprovalDecisionInput {
  approvalId: string;
  decision: ApprovalDecision;
  decisionReason?: string;
}

export async function decideApproval(
  input: ApprovalDecisionInput,
): Promise<ApprovalDecisionResponse> {
  const response = await apiFetch<ApprovalDecisionResponse>(
    `/api/backend/approvals/${encodeURIComponent(input.approvalId)}`,
    jsonRequest(
      {
        decision: input.decision,
        ...(input.decisionReason
          ? { decision_reason: input.decisionReason }
          : {}),
      },
      { method: "POST" },
    ),
  );

  return {
    ...response,
    resumed_event: response.resumed_event
      ? normalizeConversationEvent(response.resumed_event)
      : null,
  };
}
