"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Clock3, RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  getChatErrorPresentation,
  remainingRetrySeconds,
} from "@/features/chat/quota";
import { ApiError } from "@/lib/api/errors";

export function ChatErrorBanner({
  error,
  retrying,
  onRetry,
  onBlockedChange,
}: {
  error: ApiError;
  retrying: boolean;
  onRetry: () => void;
  onBlockedChange: (blocked: boolean) => void;
}) {
  const presentation = useMemo(() => getChatErrorPresentation(error), [error]);
  const [elapsed, setElapsed] = useState(0);
  const remaining = remainingRetrySeconds(
    presentation.retryAfterSeconds,
    elapsed,
  );
  const blocked = presentation.kind === "rate" && remaining > 0;

  useEffect(() => {
    setElapsed(0);
    if (!presentation.retryAfterSeconds) return;
    const timer = window.setInterval(
      () => setElapsed((current) => current + 1),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [presentation.retryAfterSeconds]);

  useEffect(() => {
    onBlockedChange(blocked);
    return () => onBlockedChange(false);
  }, [blocked, onBlockedChange]);

  const quota = presentation.kind !== "general";
  const Icon = presentation.kind === "rate" ? Clock3 : AlertTriangle;

  return (
    <Alert tone={quota ? "warning" : "error"} className="mb-2">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <AlertTitle>{presentation.title}</AlertTitle>
          <AlertDescription>
            {presentation.message}
            {blocked ? ` Retry available in ${remaining}s.` : ""}
            {error.requestId ? (
              <span className="mt-1 block font-mono text-[11px]">
                Request ID: {error.requestId}
              </span>
            ) : null}
          </AlertDescription>
        </div>
        {presentation.retryable ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            disabled={blocked}
            loading={retrying}
            onClick={onRetry}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {blocked ? `${remaining}s` : "Retry"}
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}
