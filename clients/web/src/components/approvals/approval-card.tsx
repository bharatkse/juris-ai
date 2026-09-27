"use client";

import { useEffect, useState } from "react";
import {
  Ban,
  CheckCircle2,
  Clock3,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  effectiveApprovalStatus,
  formatApprovalCountdown,
  secondsUntilApprovalExpiry,
} from "@/features/approvals/logic";
import type {
  ApprovalDecision,
  ApprovalMetadata,
  ApprovalStatus,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

const statusConfig: Record<
  Exclude<ApprovalStatus, "waiting">,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  approved: {
    label: "Approved",
    className: "border-success-600/30 bg-success-50 text-success-600",
    icon: CheckCircle2,
  },
  rejected: {
    label: "Rejected",
    className: "border-danger-600/30 bg-danger-50 text-danger-600",
    icon: XCircle,
  },
  expired: {
    label: "Expired",
    className: "border-danger-600/30 bg-danger-50 text-danger-600",
    icon: Clock3,
  },
  edited: {
    label: "Updated",
    className: "border-success-600/30 bg-success-50 text-success-600",
    icon: CheckCircle2,
  },
};

export function ApprovalCard({
  approval,
  pending = false,
  error,
  onDecision,
}: {
  approval: ApprovalMetadata;
  pending?: boolean;
  error?: string | null;
  onDecision: (
    decision: ApprovalDecision,
    decisionReason?: string,
  ) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [now, setNow] = useState(Date.now());
  const status = effectiveApprovalStatus(approval, now);
  const seconds = secondsUntilApprovalExpiry(approval.expires_at, now);
  const countdown = formatApprovalCountdown(seconds);

  useEffect(() => {
    const initialSeconds = secondsUntilApprovalExpiry(approval.expires_at);
    if (
      approval.status !== "waiting" ||
      initialSeconds === null ||
      initialSeconds === 0
    ) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [approval.expires_at, approval.status]);

  if (status !== "waiting") {
    const config = statusConfig[status];
    const Icon = config.icon;
    return (
      <div
        className={cn(
          "mt-5 flex items-center gap-2 rounded-md border px-3 py-2.5 font-sans text-sm",
          config.className,
        )}
        role="status"
      >
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        <span className="font-semibold">{config.label}</span>
        <span className="text-xs opacity-80">
          {status === "approved"
            ? "The external action was authorized."
            : status === "rejected"
              ? "The external action was not authorized."
              : status === "expired"
                ? "Send a new message to request this action again."
                : "The approval was updated."}
        </span>
      </div>
    );
  }

  return (
    <section
      className="mt-5 rounded-md border border-gold-600/35 border-l-[3px] border-l-gold-600 bg-gold-100/30 p-4 font-sans"
      aria-labelledby={`approval-${approval.approval_id}-title`}
    >
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gold-100 text-gold-600">
          <ShieldAlert className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3
              id={`approval-${approval.approval_id}-title`}
              className="text-sm font-semibold text-ink-950"
            >
              Approval required
            </h3>
            {countdown ? (
              <span className="flex items-center gap-1 font-mono text-xs text-ink-600">
                <Clock3 className="size-3.5" aria-hidden="true" />
                expires in {countdown}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-5 text-ink-600">
            The assistant wants to take an external action. Review it before it
            runs.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <Label htmlFor={`approval-${approval.approval_id}-reason`}>
          Decision reason (optional)
        </Label>
        <Input
          id={`approval-${approval.approval_id}-reason`}
          value={reason}
          maxLength={500}
          disabled={pending}
          placeholder="Add context for this decision"
          onChange={(event) => setReason(event.target.value)}
        />
      </div>

      {error ? (
        <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-danger-600" role="alert">
          <Ban className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="gold"
          size="sm"
          loading={pending}
          onClick={() =>
            void onDecision("approve", reason.trim() || undefined)
          }
        >
          Approve
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-danger-600/35 text-danger-600 hover:bg-danger-50"
          disabled={pending}
          onClick={() =>
            void onDecision("reject", reason.trim() || undefined)
          }
        >
          Reject
        </Button>
      </div>
    </section>
  );
}
