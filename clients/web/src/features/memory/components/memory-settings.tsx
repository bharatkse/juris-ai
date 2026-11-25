"use client";

import { useState } from "react";
import { Brain, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { COPY } from "@/constants/copy";
import {
  flattenMemories,
  useDeleteMemory,
  useMemories,
  useMemorySettings,
  useUpdateMemorySettings,
} from "@/features/memory/queries";
import { ApiError } from "@/lib/api/errors";
import type { MemoryItem } from "@/types/api";

function MemoryListSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading memories">
      {[1, 2, 3].map((key) => (
        <Skeleton key={key} className="h-20 w-full" />
      ))}
    </div>
  );
}

function MemoryRow({
  item,
  onDelete,
  pending,
}: {
  item: MemoryItem;
  onDelete: () => void;
  pending: boolean;
}) {
  return (
    <li className="rounded-md border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {item.kind} · {item.status}
          </p>
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">
            {item.content}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Saved {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0 text-danger"
          aria-label="Delete this memory"
          disabled={pending}
          onClick={onDelete}
        >
          <Trash2 className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </li>
  );
}

export function MemorySettingsPanel() {
  const settings = useMemorySettings();
  const update = useUpdateMemorySettings();
  const memories = useMemories(Boolean(settings.data?.enabled));
  const remove = useDeleteMemory();
  const [confirmOff, setConfirmOff] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MemoryItem | null>(null);
  const items = flattenMemories(memories.data);

  async function setEnabled(enabled: boolean) {
    try {
      await update.mutateAsync(enabled);
      toast.success(enabled ? "Memory turned on." : "Memory turned off.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not update memory.",
      );
    }
  }

  return (
    <div className="space-y-5">
      {settings.error && !settings.data ? (
        <Alert tone="error">
          <AlertTitle>Could not load memory settings</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            {settings.error instanceof ApiError
              ? settings.error.message
              : "Check your connection and try again."}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void settings.refetch()}
            >
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <Brain className="mb-2 size-5 text-primary" aria-hidden="true" />
          <CardTitle>Long-term memory</CardTitle>
          <CardDescription>
            When on, the assistant may save short facts you state and reuse
            them later. Turning it off deletes every saved memory.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          {settings.isPending ? (
            <Skeleton className="h-10 w-40" />
          ) : (
            <>
              <p className="text-sm">
                Memory is{" "}
                <strong>{settings.data?.enabled ? "on" : "off"}</strong>
                {settings.data?.consent_updated_at
                  ? ` · updated ${new Date(settings.data.consent_updated_at).toLocaleString()}`
                  : ""}
              </p>
              {settings.data?.enabled ? (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  loading={update.isPending}
                  onClick={() => setConfirmOff(true)}
                >
                  Turn off
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  loading={update.isPending}
                  onClick={() => void setEnabled(true)}
                >
                  Turn on
                </Button>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {settings.data?.enabled ? (
        <Card>
          <CardHeader>
            <CardTitle>Saved memories</CardTitle>
            <CardDescription>
              Newest first. Expired items are removed by the API before this
              list is built.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {memories.isPending ? (
              <MemoryListSkeleton />
            ) : memories.error ? (
              <Alert tone="error">
                <AlertTitle>Could not load memories</AlertTitle>
                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void memories.refetch()}
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Retry
                  </Button>
                </AlertDescription>
              </Alert>
            ) : items.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No saved memories yet.
              </p>
            ) : (
              <ul className="space-y-3">
                {items.map((item) => (
                  <MemoryRow
                    key={item.id}
                    item={item}
                    pending={remove.isPending}
                    onDelete={() => setDeleteTarget(item)}
                  />
                ))}
              </ul>
            )}
            {memories.hasNextPage ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-4"
                disabled={memories.isFetchingNextPage}
                onClick={() => memories.fetchNextPage()}
              >
                {memories.isFetchingNextPage ? (
                  <LoaderCircle className="size-3.5 animate-spin" />
                ) : null}
                Load more
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmOff}
        onOpenChange={setConfirmOff}
        title="Turn memory off?"
        description={COPY.memoryOffWarning}
        confirmLabel="Turn off and delete"
        loading={update.isPending}
        onConfirm={() => void setEnabled(false)}
      />
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete this memory?"
        description="This fact will be removed permanently."
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await remove.mutateAsync(deleteTarget.id);
            setDeleteTarget(null);
            toast.success("Memory deleted.");
          } catch (error) {
            toast.error(
              error instanceof Error ? error.message : "Could not delete.",
            );
          }
        }}
      />
    </div>
  );
}
