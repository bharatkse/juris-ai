"use client";

import { useEffect, useState } from "react";
import {
  Ban,
  CheckCircle2,
  Clock3,
  Pencil,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { approvalToolPayload } from "@/features/approvals/api";
import {
  effectiveApprovalStatus,
  formatApprovalCountdown,
  secondsUntilApprovalExpiry,
} from "@/features/approvals/logic";
import { COPY } from "@/constants/copy";
import type {
  ApprovalDecision,
  ApprovalMetadata,
  ApprovalStatus,
} from "@/types/api";
import { cn } from "@/lib/utils";

const statusConfig: Record<
  Exclude<ApprovalStatus, "waiting">,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  approved: {
    label: "Approved",
    className: "border-success/30 bg-success/15 text-success",
    icon: CheckCircle2,
  },
  rejected: {
    label: "Rejected",
    className: "border-danger/30 bg-danger/15 text-danger",
    icon: XCircle,
  },
  expired: {
    label: "Expired",
    className: "border-danger/30 bg-danger/15 text-danger",
    icon: Clock3,
  },
  edited: {
    label: "Updated",
    className: "border-success/30 bg-success/15 text-success",
    icon: CheckCircle2,
  },
};

function prettyPayload(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function ApprovalCard({
  approval,
  pending = false,
  error,
  onDecision,
  onResume,
}: {
  approval: ApprovalMetadata;
  pending?: boolean;
  error?: string | null;
  onDecision: (
    decision: ApprovalDecision,
    options?: {
      reason?: string;
      editedPayload?: Record<string, unknown>;
    },
  ) => Promise<void>;
  onResume?: (force?: boolean) => Promise<void>;
}) {
  const payload = approvalToolPayload(approval);
  const [reason, setReason] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() =>
    payload != null ? prettyPayload(payload) : "{\n  \n}",
  );
  const [parseError, setParseError] = useState<string | null>(null);
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
          "mt-5 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2.5 font-sans text-sm",
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
        {approval.resume_status ? (
          <span className="w-full text-xs opacity-80">
            Resume: {approval.resume_status}
          </span>
        ) : null}
        {onResume && status !== "expired" ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            loading={pending}
            onClick={() => void onResume(false)}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Retry resume
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <section
      className="mt-5 rounded-md border border-primary/35 border-l-[3px] border-l-primary bg-citation/30 p-4 font-sans"
      aria-labelledby={`approval-${approval.approval_id}-title`}
    >
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-citation text-primary">
          <ShieldAlert className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3
              id={`approval-${approval.approval_id}-title`}
              className="text-sm font-semibold text-foreground"
            >
              Approval required
            </h3>
            {countdown ? (
              <span className="flex items-center gap-1 font-mono text-xs text-muted-foreground">
                <Clock3 className="size-3.5" aria-hidden="true" />
                expires in {countdown}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Review the exact payload below. Approve runs that payload; Edit
            sends a replacement JSON as <code>edited_payload</code>.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          Tool payload
        </p>
        {payload == null && !editing ? (
          <p className="text-xs leading-5 text-muted-foreground" role="note">
            {COPY.approvalPayloadMissing}
          </p>
        ) : editing ? (
          <Textarea
            aria-label="Edited tool payload"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setParseError(null);
            }}
            disabled={pending}
            className="min-h-32 font-mono text-xs"
          />
        ) : (
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-md border border-border bg-surface p-3 font-mono text-xs leading-5">
            {prettyPayload(payload)}
          </pre>
        )}
        {parseError ? (
          <p className="mt-2 text-xs text-danger" role="alert">
            {parseError}
          </p>
        ) : null}
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
        <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-danger" role="alert">
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
            void onDecision("approve", {
              reason: reason.trim() || undefined,
            })
          }
        >
          Approve
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-danger/35 text-danger hover:bg-danger/15"
          disabled={pending}
          onClick={() =>
            void onDecision("reject", {
              reason: reason.trim() || undefined,
            })
          }
        >
          Reject
        </Button>
        {editing ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={pending}
            onClick={() => {
              try {
                const parsed = JSON.parse(draft) as unknown;
                if (
                  typeof parsed !== "object" ||
                  parsed === null ||
                  Array.isArray(parsed)
                ) {
                  setParseError("edited_payload must be a JSON object.");
                  return;
                }
                void onDecision("edit", {
                  reason: reason.trim() || undefined,
                  editedPayload: parsed as Record<string, unknown>,
                });
              } catch {
                setParseError("Payload must be valid JSON.");
              }
            }}
          >
            Submit edit
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={pending}
            onClick={() => setEditing(true)}
          >
            <Pencil className="size-3.5" aria-hidden="true" />
            Edit
          </Button>
        )}
      </div>
    </section>
  );
}
