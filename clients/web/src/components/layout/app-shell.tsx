"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Check, Menu, Pencil, X } from "lucide-react";
import { toast } from "sonner";

import { AccountMenu } from "@/components/layout/account-menu";
import { ConversationSidebar } from "@/components/layout/conversation-sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useCurrentUser } from "@/features/auth/use-current-user";
import {
  useConversation,
  useRenameConversation,
} from "@/features/conversations/queries";

function pageTitle(pathname: string, conversationTitle?: string): string {
  if (pathname === "/app/settings") {
    return "Settings";
  }
  if (pathname.startsWith("/app/c/")) {
    return conversationTitle || "Conversation";
  }
  return "New conversation";
}

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const pathname = usePathname();
  const router = useRouter();
  const user = useCurrentUser();
  const conversationId = pathname.startsWith("/app/c/")
    ? decodeURIComponent(pathname.slice("/app/c/".length))
    : undefined;
  const conversation = useConversation(conversationId);
  const renameConversation = useRenameConversation();
  const title = pageTitle(pathname, conversation.data?.title);

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
  }, [conversation.data?.title, conversationId]);

  useEffect(() => {
    document.title = `${title} | Juris AI`;
  }, [title]);

  async function submitRename() {
    const nextTitle = draftTitle.trim();
    if (!conversationId || !nextTitle || nextTitle === conversation.data?.title) {
      setRenaming(false);
      return;
    }

    try {
      await renameConversation.mutateAsync({
        id: conversationId,
        title: nextTitle,
      });
      setRenaming(false);
      toast.success("Conversation renamed.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not rename conversation.",
      );
    }
  }

  return (
    <div className="flex h-dvh min-h-[640px] overflow-hidden bg-paper-50">
      <ConversationSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user.data}
        userLoading={user.isPending}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-line-200 bg-paper-50 px-4 sm:px-6 lg:h-20 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 lg:hidden"
              aria-controls="conversation-sidebar"
              aria-expanded={sidebarOpen}
              aria-label="Open sidebar"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="size-5" aria-hidden="true" />
            </Button>
            <div className="min-w-0">
              {renaming && conversationId ? (
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
                    className="h-9 min-w-0"
                    aria-label="Conversation title"
                    autoFocus
                    disabled={renameConversation.isPending}
                  />
                  <Button
                    type="submit"
                    variant="ghost"
                    size="icon"
                    className="size-9 shrink-0"
                    aria-label="Save title"
                    loading={renameConversation.isPending}
                  >
                    <Check className="size-4" aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-9 shrink-0"
                    aria-label="Cancel rename"
                    disabled={renameConversation.isPending}
                    onClick={() => setRenaming(false)}
                  >
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </form>
              ) : (
                <div className="flex min-w-0 items-center gap-1">
                  <p className="truncate text-sm font-semibold text-ink-950 sm:text-base">
                    {title}
                  </p>
                  {conversation.data ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      aria-label="Rename conversation"
                      title="Rename conversation"
                      onClick={() => setRenaming(true)}
                    >
                      <Pencil className="size-3.5" aria-hidden="true" />
                    </Button>
                  ) : null}
                </div>
              )}
              <p className="hidden text-xs text-ink-400 sm:block">
                Private individual workspace
              </p>
            </div>
          </div>
          <div className="w-auto max-w-[220px] lg:hidden">
            <AccountMenu user={user.data} loading={user.isPending} />
          </div>
        </header>

        <main id="main-content" className="min-h-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
