import { apiFetch, jsonRequest } from "@/lib/api/client";
import type {
  ApprovalDecision,
  ApprovalDecisionResponse,
  ApprovalMetadata,
} from "@/types/api";

export interface ApprovalDecisionInput {
  approvalId: string;
  decision: ApprovalDecision;
  decisionReason?: string;
  editedPayload?: Record<string, unknown>;
}

export async function decideApproval(
  input: ApprovalDecisionInput,
): Promise<ApprovalDecisionResponse> {
  return apiFetch<ApprovalDecisionResponse>(
    `/api/backend/approvals/${encodeURIComponent(input.approvalId)}`,
    jsonRequest(
      {
        decision: input.decision,
        ...(input.decisionReason
          ? { decision_reason: input.decisionReason }
          : {}),
        ...(input.editedPayload
          ? { edited_payload: input.editedPayload }
          : {}),
      },
      { method: "POST" },
    ),
  );
}

export async function retryApprovalResume(
  approvalId: string,
  force = false,
): Promise<ApprovalDecisionResponse> {
  const params = force ? "?force=true" : "";
  return apiFetch<ApprovalDecisionResponse>(
    `/api/backend/approvals/${encodeURIComponent(approvalId)}/resume${params}`,
    { method: "POST" },
  );
}

export function approvalToolPayload(approval: ApprovalMetadata): unknown {
  if (approval.payload != null) return approval.payload;
  if (approval.action != null) return approval.action;
  return null;
}
