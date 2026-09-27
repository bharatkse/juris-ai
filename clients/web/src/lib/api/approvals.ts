import { apiFetch, jsonRequest } from "@/lib/api/client";
import { normalizeConversationEvent } from "@/lib/api/conversations";
import type {
  ApprovalDecision,
  ApprovalDecisionResponse,
} from "@/lib/api/types";

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
