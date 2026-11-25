"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Archive,
  Brain,
  LoaderCircle,
  MessageSquareText,
  PanelLeft,
  Plus,
  RefreshCw,
  Search,
  Settings,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/brand/logo";
import { AccountMenu } from "@/components/layout/account-menu";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ThemeToggle } from "@/features/theme/theme-toggle";
import {
  filterConversations,
  flattenConversations,
  groupConversationsByRecency,
  useArchiveConversation,
  useConversations,
  useCreateConversation,
} from "@/features/conversations/queries";
import type { Conversation, User } from "@/types/api";
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

const NAV = [
  { href: "/app", label: "Chats", icon: MessageSquareText, match: "chats" },
  { href: "/app/memory", label: "Memory", icon: Brain, match: "memory" },
  { href: "/app/settings", label: "Settings", icon: Settings, match: "settings" },
] as const;

export function ConversationSidebar({
  open,
  collapsed,
  onClose,
  onToggleCollapsed,
  user,
  userLoading,
}: {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapsed: () => void;
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
  const grouped = groupConversationsByRecency(filtered);
  const rail = collapsed;

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

  function navActive(match: (typeof NAV)[number]["match"]): boolean {
    if (match === "chats") {
      return pathname === "/app" || pathname.startsWith("/app/c/");
    }
    if (match === "memory") return pathname === "/app/memory";
    return pathname === "/app/settings";
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close navigation"
        className={cn(
          "fixed inset-0 z-40 bg-foreground/40 transition-opacity duration-fast md:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        id="conversation-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[transform,width] duration-fast md:static md:z-auto",
          rail ? "md:w-14" : "md:w-[260px]",
          open ? "w-[min(86vw,260px)] translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
        aria-label="Workspace navigation"
      >
        <div className={cn("flex h-12 shrink-0 items-center px-3", rail && "md:justify-center")}>
          <Link
            href="/app"
            onClick={onClose}
            aria-label="Juris AI workspace"
            className={cn(rail && "md:hidden")}
          >
            <Logo inverse compact={false} />
          </Link>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="ml-auto text-sidebar-foreground hover:bg-hover md:hidden"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X className="size-5" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="ml-auto hidden size-9 text-sidebar-foreground hover:bg-hover md:inline-flex"
            onClick={onToggleCollapsed}
            aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={rail}
          >
            <PanelLeft className="size-4" aria-hidden="true" />
          </Button>
        </div>

        <div className={cn("px-3", rail && "md:px-2")}>
          <Button
            type="button"
            variant="gold"
            className={cn("w-full justify-start", rail && "md:justify-center md:px-0")}
            loading={createConversation.isPending}
            onClick={startNewChat}
            aria-label="New chat"
          >
            <Plus className="size-4" aria-hidden="true" />
            <span className={cn(rail && "md:hidden")}>
              {createConversation.isPending ? "Creating…" : "New chat"}
            </span>
          </Button>
          <div className={cn("relative mt-3", rail && "md:hidden")}>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-sidebar-muted"
              aria-hidden="true"
            />
            <input
              type="search"
              aria-label="Search conversations"
              placeholder="Search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-9 w-full rounded-md border border-sidebar-border bg-surface pl-9 pr-3 text-sm text-sidebar-foreground outline-none placeholder:text-sidebar-muted focus:border-primary focus:ring-2 focus:ring-ring/25"
            />
          </div>
        </div>

        <nav className={cn("mt-3 space-y-0.5 px-2", rail && "md:px-1.5")} aria-label="Primary">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = navActive(item.match);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                title={item.label}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-2 text-sm outline-none transition-colors duration-fast focus-visible:ring-2 focus-visible:ring-ring",
                  rail && "md:justify-center",
                  active
                    ? "bg-hover text-sidebar-foreground"
                    : "text-sidebar-muted hover:bg-hover hover:text-sidebar-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                <span className={cn(rail && "md:hidden")}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <nav
          className={cn("mt-4 min-h-0 flex-1 overflow-y-auto px-2", rail && "md:hidden")}
          aria-label="Recents"
        >
          <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-sidebar-muted">
            Recents
          </p>
          <div className="mt-2">
            {conversations.isPending ? (
              <ConversationListSkeleton />
            ) : conversations.isError && !conversations.data ? (
              <div className="mx-1 rounded-md border border-danger/35 bg-danger/10 px-4 py-5 text-center">
                <p className="text-sm font-medium">Could not load conversations</p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  onClick={() => conversations.refetch()}
                >
                  <RefreshCw className="size-3.5" aria-hidden="true" />
                  Retry
                </Button>
              </div>
            ) : loaded.length === 0 ? (
              <div className="mx-1 rounded-md px-4 py-7 text-center">
                <MessageSquareText
                  className="mx-auto size-5 text-primary"
                  aria-hidden="true"
                />
                <p className="mt-3 text-sm font-medium">No threads yet</p>
                <p className="mt-1 text-xs leading-5 text-sidebar-muted">
                  Start your first research thread.
                </p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-4 py-7 text-center">
                <p className="text-sm text-sidebar-muted">No matching threads.</p>
                <button
                  type="button"
                  className="mt-2 text-xs font-medium text-primary underline underline-offset-4"
                  onClick={() => setSearch("")}
                >
                  Clear search
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {grouped.map((bucket) => (
                  <div key={bucket.group}>
                    <p className="px-2 pb-1 text-[11px] font-medium text-sidebar-muted">
                      {bucket.label}
                    </p>
                    <div className="space-y-0.5">
                      {bucket.items.map((conversation) => {
                        const href = `/app/c/${conversation.id}`;
                        const active = pathname === href;
                        return (
                          <div
                            key={conversation.id}
                            className={cn(
                              "group relative rounded-md transition-colors duration-fast",
                              active
                                ? "bg-hover text-sidebar-foreground"
                                : "text-sidebar-muted hover:bg-hover hover:text-sidebar-foreground",
                            )}
                          >
                            <Link
                              href={href}
                              onClick={onClose}
                              aria-current={active ? "page" : undefined}
                              className="block min-w-0 rounded-md px-2 py-2 pr-9 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              <span className="block truncate text-sm font-medium text-sidebar-foreground">
                                {conversation.title}
                              </span>
                            </Link>
                            <button
                              type="button"
                              className="absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-sm text-sidebar-muted opacity-100 outline-none hover:bg-danger/15 hover:text-danger focus-visible:ring-2 focus-visible:ring-ring md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                              aria-label={`Archive ${conversation.title}`}
                              onClick={() => setArchiveTarget(conversation)}
                            >
                              <Archive className="size-3.5" aria-hidden="true" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}

                {conversations.hasNextPage && !search.trim() ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-2 w-full"
                    disabled={conversations.isFetchingNextPage}
                    onClick={() => conversations.fetchNextPage()}
                  >
                    {conversations.isFetchingNextPage ? (
                      <LoaderCircle
                        className="size-3.5 animate-spin"
                        aria-hidden="true"
                      />
                    ) : null}
                    {conversations.isFetchingNextPage ? "Loading…" : "Load more"}
                  </Button>
                ) : null}
              </div>
            )}
          </div>
        </nav>

        <div className={cn("mt-auto border-t border-sidebar-border p-2", rail && "md:px-1.5")}>
          <div className={cn("mb-1 flex items-center", rail ? "md:justify-center" : "justify-between px-1")}>
            <span className={cn("text-xs text-sidebar-muted", rail && "md:hidden")}>
              Theme
            </span>
            <ThemeToggle />
          </div>
          <AccountMenu user={user} loading={userLoading} inverse compact={rail} />
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
