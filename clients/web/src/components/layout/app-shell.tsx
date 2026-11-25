"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Brain, Check, Ellipsis, Menu, PanelLeft, Pencil, X } from "lucide-react";
import { toast } from "sonner";

import { AccountMenu } from "@/components/layout/account-menu";
import { ConversationSidebar } from "@/components/layout/conversation-sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useCurrentUser } from "@/features/auth/use-current-user";
import { features } from "@/config/features";
import {
  useConversation,
  useSetConversationMemory,
} from "@/features/conversations/queries";
import { cn } from "@/lib/utils";

const SIDEBAR_COLLAPSED_KEY = "juris-sidebar-collapsed";

function pageTitle(pathname: string, conversationTitle?: string): string {
  if (pathname === "/app/settings") {
    return "Settings";
  }
  if (pathname === "/app/memory") {
    return "Memory";
  }
  if (pathname.startsWith("/app/c/")) {
    return conversationTitle || "Conversation";
  }
  return "New conversation";
}

function readCollapsed(): boolean {
  try {
    return globalThis.localStorage?.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const pathname = usePathname();
  const router = useRouter();
  const user = useCurrentUser();
  const conversationId = pathname.startsWith("/app/c/")
    ? decodeURIComponent(pathname.slice("/app/c/".length))
    : undefined;
  const conversation = useConversation(conversationId);
  const setMemory = useSetConversationMemory();
  const title = pageTitle(pathname, conversation.data?.title);

  useEffect(() => {
    setSidebarCollapsed(readCollapsed());
  }, []);

  useEffect(() => {
    function redirectToLogin() {
      const next = encodeURIComponent(
        `${window.location.pathname}${window.location.search}`,
      );
      router.replace(`/login?next=${next}`);
      router.refresh();
    }

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
    if (user.error instanceof ApiError && user.error.httpStatus === 401) {
      redirectToLogin();
    }

    return () =>
      window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
  }, [router, user.error]);

  useEffect(() => {
    setDraftTitle(conversation.data?.title ?? "");
    setRenaming(false);
    setActionsOpen(false);
  }, [conversation.data?.title, conversationId]);

  useEffect(() => {
    document.title = `${title} | Juris AI`;
  }, [title]);

  function toggleCollapsed() {
    setSidebarCollapsed((current) => {
      const next = !current;
      try {
        globalThis.localStorage?.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  async function submitRename() {
    const nextTitle = draftTitle.trim();
    if (!conversationId || !nextTitle || nextTitle === conversation.data?.title) {
      setRenaming(false);
      return;
    }

    toast.error("Renaming is not available: the API has no PATCH conversation route.");
    setRenaming(false);
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <ConversationSidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapsed={toggleCollapsed}
        user={user.data}
        userLoading={user.isPending}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-2 px-3 sm:px-4">
          <div className="flex min-w-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-9 shrink-0 md:hidden"
              aria-controls="conversation-sidebar"
              aria-expanded={sidebarOpen}
              aria-label="Open sidebar"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="size-5" aria-hidden="true" />
            </Button>
            {sidebarCollapsed ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="hidden size-9 md:inline-flex"
                aria-label="Expand sidebar"
                onClick={toggleCollapsed}
              >
                <PanelLeft className="size-4" aria-hidden="true" />
              </Button>
            ) : null}
            <div className="min-w-0">
              {features.conversationRename && renaming && conversationId ? (
                <form
                  className="flex max-w-[min(48vw,420px)] items-center gap-1"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitRename();
                  }}
                >
                  <Input
                    value={draftTitle}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        event.preventDefault();
                        setDraftTitle(conversation.data?.title ?? "");
                        setRenaming(false);
                      }
                    }}
                    maxLength={255}
                    className="h-8 min-w-0"
                    aria-label="Conversation title"
                    autoFocus
                  />
                  <Button
                    type="submit"
                    variant="ghost"
                    size="icon"
                    className="size-8 shrink-0"
                    aria-label="Save title"
                  >
                    <Check className="size-4" aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-8 shrink-0"
                    aria-label="Cancel rename"
                    onClick={() => setRenaming(false)}
                  >
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </form>
              ) : (
                <button
                  type="button"
                  className={cn(
                    "flex min-w-0 max-w-full items-center gap-1 rounded-md px-1.5 py-1 text-left outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring",
                    !features.conversationRename && "cursor-default hover:bg-transparent",
                  )}
                  onClick={() => {
                    if (features.conversationRename && conversation.data) {
                      setRenaming(true);
                    }
                  }}
                  aria-label={
                    features.conversationRename
                      ? "Rename conversation"
                      : undefined
                  }
                >
                  <span className="truncate text-sm font-medium text-foreground">
                    {title}
                  </span>
                  {features.conversationRename && conversation.data ? (
                    <Pencil className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
                  ) : null}
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {conversation.data ? (
              <div className="relative">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-9"
                  aria-expanded={actionsOpen}
                  aria-haspopup="menu"
                  aria-label="Conversation actions"
                  onClick={() => setActionsOpen((open) => !open)}
                >
                  <Ellipsis className="size-4" aria-hidden="true" />
                </Button>
                {actionsOpen ? (
                  <div
                    role="menu"
                    className="absolute right-0 z-30 mt-1 w-52 rounded-md border border-border bg-surface p-1 shadow-sm"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm hover:bg-hover"
                      onClick={() => {
                        setActionsOpen(false);
                        void setMemory
                          .mutateAsync({
                            id: conversation.data!.id,
                            memoryDisabled: !conversation.data!.memory_disabled,
                          })
                          .then(() =>
                            toast.success(
                              conversation.data?.memory_disabled
                                ? "Memory allowed for this conversation."
                                : "New messages will not be saved to memory.",
                            ),
                          )
                          .catch((error: unknown) =>
                            toast.error(
                              error instanceof Error
                                ? error.message
                                : "Could not update conversation memory.",
                            ),
                          );
                      }}
                    >
                      <Brain className="size-4" aria-hidden="true" />
                      {conversation.data.memory_disabled
                        ? "Allow memory"
                        : "Don't remember this"}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="md:hidden">
              <AccountMenu user={user.data} loading={user.isPending} />
            </div>
          </div>
        </header>

        <main id="main-content" className="min-h-0 flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
