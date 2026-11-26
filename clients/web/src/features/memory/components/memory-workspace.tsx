"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Copy, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DeviceHint } from "@/components/ui/device-hint";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { COPY } from "@/constants/copy";
import {
  useClearMemories,
  useCreateMemory,
  useDeleteMemory,
  useMemories,
  useMemory,
  useMemoryPersistence,
  useMemorySettings,
  useUpdateMemory,
  useUpdateMemorySettings,
} from "@/features/memory/queries";
import type { MemoryRecord, MemorySort } from "@/features/memory/types";
import { cn } from "@/lib/utils";

export function MemoryWorkspace({ selectedId }: { selectedId?: string }) {
  const router = useRouter();
  const settings = useMemorySettings();
  const updateSettings = useUpdateMemorySettings();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<MemorySort>("updated");
  const [kind, setKind] = useState("");
  const memories = useMemories(
    { search, sort, kind: kind || undefined },
    Boolean(settings.data?.enabled),
  );
  const selected = useMemory(selectedId);
  const create = useCreateMemory();
  const update = useUpdateMemory();
  const remove = useDeleteMemory();
  const clearAll = useClearMemories();
  const persistence = useMemoryPersistence();
  const [confirmOff, setConfirmOff] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [editing, setEditing] = useState(false);

  const items = useMemo(() => memories.data ?? [], [memories.data]);
  const kinds = useMemo(
    () => Array.from(new Set(items.map((item) => item.kind))).sort(),
    [items],
  );

  const mobileDetail = Boolean(selectedId);

  async function setEnabled(enabled: boolean) {
    try {
      await updateSettings.mutateAsync(enabled);
      toast.success(enabled ? "Memory turned on." : "Memory turned off.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update memory.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.02em]">Memory</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Facts the assistant can reuse across conversations.
        </p>
        <DeviceHint persistence={persistence} />
      </div>

      {settings.error && !settings.data ? (
        <Alert tone="error">
          <AlertTitle>Could not load memory settings</AlertTitle>
          <AlertDescription>
            <Button type="button" variant="outline" size="sm" onClick={() => void settings.refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <div>
          <p className="text-sm font-medium">Use memory in conversations</p>
          <p className="text-sm text-muted-foreground">
            Turning this off deletes every saved memory on the server.
          </p>
        </div>
        {settings.isPending ? (
          <Skeleton className="h-6 w-10" />
        ) : (
          <Switch
            checked={Boolean(settings.data?.enabled)}
            label="Use memory in conversations"
            onCheckedChange={(checked) => {
              if (!checked) setConfirmOff(true);
              else void setEnabled(true);
            }}
          />
        )}
      </div>

      {settings.data?.enabled ? (
        <div className="flex min-h-[28rem] overflow-hidden rounded-lg border border-border bg-surface md:min-h-[32rem]">
          <div
            className={cn(
              "w-full border-border md:w-[240px] md:shrink-0 md:border-r",
              mobileDetail && "hidden md:flex md:flex-col",
              !mobileDetail && "flex flex-col",
            )}
          >
            <div className="space-y-2 border-b border-border p-3">
              <Button
                type="button"
                size="sm"
                className="w-full"
                onClick={() => {
                  setAdding(true);
                  setDraftTitle("");
                  setDraftContent("");
                }}
              >
                <Plus className="size-4" aria-hidden="true" />
                Add memory
              </Button>
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search"
                aria-label="Search memories"
              />
              <div className="flex gap-2">
                <select
                  className="h-9 flex-1 rounded-md border border-border bg-surface px-2 text-xs"
                  value={sort}
                  onChange={(event) => setSort(event.target.value as MemorySort)}
                  aria-label="Sort memories"
                >
                  <option value="updated">Updated</option>
                  <option value="created">Created</option>
                </select>
                <select
                  className="h-9 flex-1 rounded-md border border-border bg-surface px-2 text-xs"
                  value={kind}
                  onChange={(event) => setKind(event.target.value)}
                  aria-label="Filter by source"
                >
                  <option value="">All sources</option>
                  {kinds.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {memories.isPending ? (
                <div className="space-y-2 p-3" aria-label="Loading memories">
                  <Skeleton className="h-14" />
                  <Skeleton className="h-14" />
                </div>
              ) : memories.error ? (
                <div className="p-3">
                  <Button type="button" variant="ghost" size="sm" onClick={() => void memories.refetch()}>
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Retry
                  </Button>
                </div>
              ) : items.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground">No saved memories yet.</p>
              ) : (
                <ul>
                  {items.map((item) => (
                    <li key={item.id}>
                      <Link
                        href={`/settings/memory/${item.id}`}
                        className={cn(
                          "block border-b border-border px-3 py-3 hover:bg-hover",
                          selectedId === item.id && "bg-hover",
                        )}
                      >
                        <p className="truncate text-sm font-medium">{item.title}</p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {item.content}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {item.kind} · {new Date(item.updated_at).toLocaleDateString()}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="border-t border-border p-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full text-danger"
                onClick={() => setConfirmClear(true)}
              >
                Clear all memory
              </Button>
            </div>
          </div>

          <div
            className={cn(
              "min-w-0 flex-1",
              !mobileDetail && "hidden md:block",
            )}
          >
            {adding ? (
              <MemoryEditor
                title={draftTitle}
                content={draftContent}
                onTitle={setDraftTitle}
                onContent={setDraftContent}
                onCancel={() => setAdding(false)}
                onSave={async () => {
                  const record = await create.mutateAsync({
                    title: draftTitle,
                    content: draftContent,
                  });
                  setAdding(false);
                  router.push(`/settings/memory/${record.id}`);
                  toast.success("Memory saved.");
                }}
                saving={create.isPending}
              />
            ) : selectedId ? (
              <MemoryDetail
                record={selected.data}
                loading={selected.isPending}
                error={selected.error}
                editing={editing}
                onEdit={() => {
                  if (selected.data) {
                    setDraftTitle(selected.data.title);
                    setDraftContent(selected.data.content);
                    setEditing(true);
                  }
                }}
                onCancel={() => setEditing(false)}
                title={draftTitle}
                content={draftContent}
                onTitle={setDraftTitle}
                onContent={setDraftContent}
                onSave={async () => {
                  await update.mutateAsync({
                    id: selectedId,
                    draft: { title: draftTitle, content: draftContent },
                  });
                  setEditing(false);
                  toast.success("Memory updated.");
                }}
                saving={update.isPending}
                onDelete={() => setDeleteId(selectedId)}
                onBack={() => router.push("/settings/memory")}
              />
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-sm text-muted-foreground">
                Select a memory or add one.
              </div>
            )}
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmOff}
        onOpenChange={setConfirmOff}
        title="Turn memory off?"
        description={COPY.memoryOffWarning}
        confirmLabel="Turn off and delete"
        loading={updateSettings.isPending}
        onConfirm={() => void setEnabled(false)}
      />
      <ConfirmDialog
        open={confirmClear}
        onOpenChange={setConfirmClear}
        title="Clear all memory?"
        description="Every saved fact will be removed."
        confirmLabel="Clear all"
        loading={clearAll.isPending}
        onConfirm={async () => {
          await clearAll.mutateAsync();
          setConfirmClear(false);
          router.push("/settings/memory");
          toast.success("Memory cleared.");
        }}
      />
      <ConfirmDialog
        open={Boolean(deleteId)}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
        title="Delete this memory?"
        description="This fact will be removed permanently."
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={async () => {
          if (!deleteId) return;
          await remove.mutateAsync(deleteId);
          setDeleteId(null);
          router.push("/settings/memory");
          toast.success("Memory deleted.");
        }}
      />
    </div>
  );
}

function MemoryEditor({
  title,
  content,
  onTitle,
  onContent,
  onCancel,
  onSave,
  saving,
}: {
  title: string;
  content: string;
  onTitle: (value: string) => void;
  onContent: (value: string) => void;
  onCancel: () => void;
  onSave: () => Promise<void>;
  saving: boolean;
}) {
  return (
    <form
      className="space-y-4 p-5"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave().catch((error: unknown) =>
          toast.error(error instanceof Error ? error.message : "Could not save."),
        );
      }}
    >
      <Input
        value={title}
        onChange={(event) => onTitle(event.target.value)}
        placeholder="Title"
        aria-label="Memory title"
      />
      <Textarea
        value={content}
        onChange={(event) => onContent(event.target.value)}
        placeholder="What should Juris AI remember?"
        rows={8}
        aria-label="Memory content"
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={saving} disabled={!content.trim()}>
          Save
        </Button>
      </div>
    </form>
  );
}

function MemoryDetail({
  record,
  loading,
  error,
  editing,
  onEdit,
  onCancel,
  title,
  content,
  onTitle,
  onContent,
  onSave,
  saving,
  onDelete,
  onBack,
}: {
  record?: MemoryRecord;
  loading: boolean;
  error: unknown;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  title: string;
  content: string;
  onTitle: (value: string) => void;
  onContent: (value: string) => void;
  onSave: () => Promise<void>;
  saving: boolean;
  onDelete: () => void;
  onBack: () => void;
}) {
  if (loading) {
    return (
      <div className="space-y-3 p-5">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-32" />
      </div>
    );
  }
  if (error || !record) {
    return (
      <div className="p-5">
        <p className="text-sm">Could not load this memory.</p>
        <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={onBack}>
          Back
        </Button>
      </div>
    );
  }

  if (editing) {
    return (
      <MemoryEditor
        title={title}
        content={content}
        onTitle={onTitle}
        onContent={onContent}
        onCancel={onCancel}
        onSave={onSave}
        saving={saving}
      />
    );
  }

  return (
    <div className="flex h-full flex-col p-5">
      <div className="mb-4 flex items-center gap-2 md:hidden">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back
        </Button>
      </div>
      <h2 className="text-lg font-semibold">{record.title}</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        {record.kind} · updated {new Date(record.updated_at).toLocaleString()}
      </p>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-6">{record.content}</p>
      {record.source_conversation_id ? (
        <Link
          href={`/app/c/${record.source_conversation_id}`}
          className="mt-4 text-sm text-primary underline underline-offset-4"
        >
          Open source conversation
        </Link>
      ) : null}
      <div className="mt-auto flex flex-wrap gap-2 pt-6">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            void navigator.clipboard.writeText(record.content);
            toast.success("Copied.");
          }}
        >
          <Copy className="size-3.5" aria-hidden="true" />
          Copy
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onEdit}>
          Edit
        </Button>
        <Button type="button" variant="destructive" size="sm" onClick={onDelete}>
          <Trash2 className="size-3.5" aria-hidden="true" />
          Delete
        </Button>
      </div>
    </div>
  );
}
