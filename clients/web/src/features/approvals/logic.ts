import type { ApprovalMetadata, ApprovalStatus } from "@/lib/api/types";

export function secondsUntilApprovalExpiry(
  expiresAt: string | undefined,
  now = Date.now(),
): number | null {
  if (!expiresAt) return null;
  const timestamp = new Date(expiresAt).getTime();
  if (!Number.isFinite(timestamp)) return null;
  return Math.max(0, Math.ceil((timestamp - now) / 1000));
}

export function effectiveApprovalStatus(
  approval: ApprovalMetadata,
  now = Date.now(),
): ApprovalStatus {
  if (
    approval.status === "waiting" &&
    secondsUntilApprovalExpiry(approval.expires_at, now) === 0
  ) {
    return "expired";
  }
  return approval.status;
}

export function formatApprovalCountdown(seconds: number | null): string | null {
  if (seconds === null) return null;
  const minutes = Math.floor(seconds / 60);
  const remainder = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${remainder}`;
}
