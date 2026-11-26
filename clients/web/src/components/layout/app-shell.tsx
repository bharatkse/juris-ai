"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Brain, Ellipsis, Menu, PanelLeft, Pin, PinOff } from "lucide-react";
import { toast } from "sonner";

import { ConversationSidebar } from "@/components/layout/conversation-sidebar";
import { ProfileMenu } from "@/components/layout/profile-menu";
import { WorkspaceHotkeys } from "@/components/layout/workspace-hotkeys";
import { Button } from "@/components/ui/button";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { defaultCapabilities } from "@/features/auth/capabilities";
import { useCurrentUser } from "@/features/auth/use-current-user";
import {
  useConversation,
  useSetConversationMemory,
} from "@/features/conversations/queries";
import { isPinned } from "@/features/pins/order";
import { usePins, useTogglePin } from "@/features/pins/queries";
import { displayTitle, useConversationTitles } from "@/features/titles/queries";

const SIDEBAR_COLLAPSED_KEY = "juris-sidebar-collapsed";

function pageTitle(
  pathname: string,
  conversationTitle?: string,
): string {
  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/projects")) return "Projects";
  if (pathname.startsWith("/app/documents")) return "Documents";
  if (pathname.startsWith("/app/approvals")) return "Plans";
  if (pathname.startsWith("/app/c/")) return conversationTitle || "Conversation";
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
  const pathname = usePathname();
  const router = useRouter();
  const user = useCurrentUser();
  const conversationId = pathname.startsWith("/app/c/")
    ? decodeURIComponent(pathname.slice("/app/c/".length).split("?")[0] ?? "")
    : undefined;
  const conversation = useConversation(conversationId);
  const titles = useConversationTitles();
  const setMemory = useSetConversationMemory();
  const pins = usePins();
  const togglePin = useTogglePin();
  const display = conversation.data
    ? displayTitle(
        conversation.data.id,
        conversation.data.title,
        titles.data,
      )
    : undefined;
  const title = pageTitle(pathname, display);

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
    setActionsOpen(false);
  }, [conversationId]);

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

  const pinTarget = conversationId
    ? ({ type: "conversation" as const, id: conversationId })
    : null;
  const pinned = pinTarget
    ? isPinned(pins.data ?? [], pinTarget)
    : false;

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <WorkspaceHotkeys />
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
            <span className="truncate px-1.5 text-sm font-medium text-foreground">
              {title}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {conversation.data && pinTarget ? (
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
                        void togglePin.mutateAsync(pinTarget);
                      }}
                    >
                      {pinned ? (
                        <PinOff className="size-4" aria-hidden="true" />
                      ) : (
                        <Pin className="size-4" aria-hidden="true" />
                      )}
                      {pinned ? "Unpin" : "Pin"}
                    </button>
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
              <ProfileMenu
                user={user.data}
                loading={user.isPending}
                capabilities={defaultCapabilities()}
              />
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
