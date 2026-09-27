"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Archive,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/brand/logo";
import { AccountMenu } from "@/components/layout/account-menu";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  filterConversations,
  flattenConversations,
  formatRelativeTime,
  useArchiveConversation,
  useConversations,
  useCreateConversation,
} from "@/features/conversations/queries";
import type { Conversation, User } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function ConversationListSkeleton() {
  return (
    <div className="space-y-2" aria-label="Loading conversations">
      {[68, 82, 58, 74].map((width) => (
        <div className="space-y-2 rounded-md px-3 py-2.5" key={width}>
          <Skeleton className="h-3" style={{ width: `${width}%` }} />
          <Skeleton className="h-2.5 w-10" />
        </div>
      ))}
    </div>
  );
}

export function ConversationSidebar({
  open,
  onClose,
  user,
  userLoading,
}: {
  open: boolean;
  onClose: () => void;
  user?: User;
  userLoading: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const conversations = useConversations();
  const createConversation = useCreateConversation();
  const archiveConversation = useArchiveConversation();
  const [search, setSearch] = useState("");
  const [archiveTarget, setArchiveTarget] = useState<Conversation | null>(null);
  const loaded = flattenConversations(conversations.data);
  const filtered = filterConversations(loaded, search);

  async function startNewChat() {
    try {
      const conversation = await createConversation.mutateAsync(undefined);
      router.push(`/app/c/${encodeURIComponent(conversation.id)}`);
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not create conversation.",
      );
    }
  }

  async function archiveSelected() {
    if (!archiveTarget) return;

    try {
      await archiveConversation.mutateAsync(archiveTarget.id);
      if (pathname === `/app/c/${archiveTarget.id}`) {
        router.replace("/app");
      }
      toast.success("Conversation archived.");
      setArchiveTarget(null);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not archive conversation.",
      );
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close navigation"
        className={cn(
          "fixed inset-0 z-40 bg-ink-950/45 transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        id="conversation-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[min(86vw,280px)] flex-col bg-ink-950 text-paper transition-transform duration-200 lg:static lg:z-auto lg:w-[260px] lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Workspace navigation"
      >
        <div className="flex h-20 items-center justify-between px-5">
          <Link href="/app" onClick={onClose} aria-label="Juris AI workspace">
            <Logo inverse />
          </Link>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="text-paper hover:bg-paper/10 hover:text-paper lg:hidden"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X className="size-5" aria-hidden="true" />
          </Button>
        </div>

        <div className="px-4">
          <Button
            type="button"
            variant="gold"
            className="w-full justify-start"
            loading={createConversation.isPending}
            onClick={startNewChat}
          >
            <Plus className="size-4" aria-hidden="true" />
            {createConversation.isPending ? "Creating…" : "New chat"}
          </Button>
          <div className="relative mt-4">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-paper/40"
              aria-hidden="true"
            />
            <input
              type="search"
              aria-label="Search conversations"
              placeholder="Search conversations"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-10 w-full rounded-md border border-paper/15 bg-paper/5 pl-9 pr-3 text-sm text-paper outline-none placeholder:text-paper/35 focus:border-gold-600 focus:ring-2 focus:ring-gold-600/25"
            />
          </div>
        </div>

        <nav className="mt-6 min-h-0 flex-1 overflow-y-auto px-3" aria-label="Conversations">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-paper/40">
            Recent
          </p>
          <div className="mt-3">
            {conversations.isPending ? (
              <ConversationListSkeleton />
            ) : conversations.isError && !conversations.data ? (
              <div className="mx-1 rounded-md border border-danger-600/35 bg-danger-600/10 px-4 py-5 text-center">
                <p className="text-sm font-medium text-paper">
                  Could not load conversations
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2 text-paper hover:bg-paper/10 hover:text-paper"
                  onClick={() => conversations.refetch()}
                >
                  <RefreshCw className="size-3.5" aria-hidden="true" />
                  Retry
                </Button>
              </div>
            ) : loaded.length === 0 ? (
              <div className="mx-1 rounded-md border border-dashed border-paper/15 px-4 py-7 text-center">
                <MessageSquareText
                  className="mx-auto size-5 text-gold-600"
                  aria-hidden="true"
                />
                <p className="mt-3 text-sm font-medium text-paper">
                  No threads yet
                </p>
                <p className="mt-1 text-xs leading-5 text-paper/45">
                  Start your first research thread.
                </p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-4 py-7 text-center">
                <p className="text-sm text-paper/70">No matching threads.</p>
                <button
                  type="button"
                  className="mt-2 text-xs font-medium text-gold-600 underline underline-offset-4"
                  onClick={() => setSearch("")}
                >
                  Clear search
                </button>
              </div>
            ) : (
              <div className="space-y-1">
                {filtered.map((conversation) => {
                  const href = `/app/c/${conversation.id}`;
                  const active = pathname === href;
                  return (
                    <div
                      key={conversation.id}
                      className={cn(
                        "group relative rounded-md transition-colors",
                        active
                          ? "bg-paper/[0.12] text-paper"
                          : "text-paper/70 hover:bg-paper/[0.07] hover:text-paper",
                      )}
                    >
                      <Link
                        href={href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        className="block min-w-0 rounded-md px-3 py-2.5 pr-10 outline-none focus-visible:ring-2 focus-visible:ring-gold-600"
                      >
                        <span className="block truncate text-sm font-medium">
                          {conversation.title}
                        </span>
                        <span
                          className={cn(
                            "mt-0.5 block text-[11px]",
                            active ? "text-gold-100/70" : "text-paper/38",
                          )}
                        >
                          {formatRelativeTime(conversation.updated_at)}
                        </span>
                      </Link>
                      <button
                        type="button"
                        className="absolute right-1.5 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-sm text-paper/55 opacity-100 outline-none hover:bg-danger-600/25 hover:text-paper focus-visible:ring-2 focus-visible:ring-gold-600 lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
                        aria-label={`Archive ${conversation.title}`}
                        onClick={() => setArchiveTarget(conversation)}
                      >
                        <Archive className="size-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  );
                })}

                {conversations.hasNextPage && !search.trim() ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-2 w-full text-paper/65 hover:bg-paper/10 hover:text-paper"
                    disabled={conversations.isFetchingNextPage}
                    onClick={() => conversations.fetchNextPage()}
                  >
                    {conversations.isFetchingNextPage ? (
                      <LoaderCircle
                        className="size-3.5 animate-spin"
                        aria-hidden="true"
                      />
                    ) : null}
                    {conversations.isFetchingNextPage
                      ? "Loading…"
                      : "Load more"}
                  </Button>
                ) : null}
              </div>
            )}
          </div>
        </nav>

        <div className="border-t border-paper/10 p-3">
          <AccountMenu user={user} loading={userLoading} inverse />
        </div>
      </aside>
      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setArchiveTarget(null);
        }}
        title="Archive this conversation?"
        description="It will leave your sidebar. You cannot reopen it in this version."
        confirmLabel="Archive"
        loading={archiveConversation.isPending}
        onConfirm={archiveSelected}
      />
    </>
  );
}
