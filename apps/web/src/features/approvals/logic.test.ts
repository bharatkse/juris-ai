import { describe, expect, it } from "vitest";

import {
  effectiveApprovalStatus,
  formatApprovalCountdown,
  secondsUntilApprovalExpiry,
} from "@/features/approvals/logic";
import type { ApprovalMetadata } from "@/lib/api/types";

const waiting: ApprovalMetadata = {
  approval_id: "approval_1",
  status: "waiting",
  expires_at: "2026-09-15T10:15:00Z",
};

describe("approval state", () => {
  it("formats an active expiry countdown", () => {
    const now = new Date("2026-09-15T10:00:00Z").getTime();
    const seconds = secondsUntilApprovalExpiry(waiting.expires_at, now);
    expect(seconds).toBe(900);
    expect(formatApprovalCountdown(seconds)).toBe("15:00");
    expect(effectiveApprovalStatus(waiting, now)).toBe("waiting");
  });

  it("turns a stale waiting approval into expired", () => {
    const now = new Date("2026-09-15T10:16:00Z").getTime();
    expect(effectiveApprovalStatus(waiting, now)).toBe("expired");
  });

  it("preserves a recorded decision", () => {
    expect(effectiveApprovalStatus({ ...waiting, status: "rejected" })).toBe(
      "rejected",
    );
  });
});
