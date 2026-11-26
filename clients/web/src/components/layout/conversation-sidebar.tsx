"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronUp,
  Ellipsis,
  LoaderCircle,
  PanelLeft,
  RefreshCw,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/brand/logo";
import { ConversationRowMenu } from "@/components/layout/conversation-row-menu";
import { MenuItem } from "@/components/layout/menu-item";
import { GroupHeader, NavIcon, NavItem, NAV_LABEL_CLASS } from "@/components/layout/nav-item";
import { ProfileMenu } from "@/components/layout/profile-menu";
import { openWorkspaceSearch } from "@/components/layout/workspace-hotkeys";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ICON_STROKE, ICONS, WORK_NAV } from "@/config/navigation";
import { defaultCapabilities } from "@/features/auth/capabilities";
import {
  flattenConversations,
  groupConversationsByRecency,
  useArchiveConversation,
  useConversations,
  useCreateConversation,
} from "@/features/conversations/queries";
import { isPinned, movePin, type PinItem } from "@/features/pins/order";
import {
  usePins,
  useReorderPins,
  useTogglePin,
} from "@/features/pins/queries";
import { recentProjects } from "@/features/projects/types";
import {
  useAttachProjectConversation,
  useProjects,
} from "@/features/projects/queries";
import {
  displayTitle,
  useConversationTitles,
  useSetConversationTitle,
} from "@/features/titles/queries";
import type { Conversation, User } from "@/types/api";
import { cn } from "@/lib/utils";

function ConversationListSkeleton() {
  return (
    <div className="space-y-1 px-2.5" aria-label="Loading conversations">
      {[68, 82, 58, 74].map((width) => (
        <div className="flex h-9 items-center" key={width}>
          <Skeleton className="h-3" style={{ width: `${width}%` }} />
        </div>
      ))}
    </div>
  );
}

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
  const titles = useConversationTitles();
  const setTitle = useSetConversationTitle();
  const pins = usePins();
  const togglePin = useTogglePin();
  const reorderPins = useReorderPins();
  const projects = useProjects();
  const attachToProject = useAttachProjectConversation();
  const [projectsOpen, setProjectsOpen] = useState(true);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [pinMenuFor, setPinMenuFor] = useState<string | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Conversation | null>(null);
  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [moveTarget, setMoveTarget] = useState<Conversation | null>(null);
  const [moveProjectId, setMoveProjectId] = useState("");
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const asideRef = useRef<HTMLElement>(null);

  const loaded = flattenConversations(conversations.data);
  const grouped = groupConversationsByRecency(loaded);
  const rail = collapsed;
  const pinItems = pins.data ?? [];
  const recent = recentProjects(projects.data ?? [], 6);

  function titleOf(conversation: Conversation): string {
    return displayTitle(conversation.id, conversation.title, titles.data);
  }

  function conversationById(id: string): Conversation | undefined {
    return loaded.find((item) => item.id === id);
  }

  useEffect(() => {
    if (!open) return;

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !asideRef.current) return;
      const nodes = asideRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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
      toast.success("Conversation deleted.");
      setArchiveTarget(null);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not delete conversation.",
      );
    }
  }

  function handleWorkItem(id: (typeof WORK_NAV)[number]["id"]) {
    if (id === "new-chat") {
      void startNewChat();
      return;
    }
    if (id === "search") {
      openWorkspaceSearch();
      onClose();
    }
  }

  const rowShell = (active: boolean) =>
    cn(
      "group relative flex h-10 min-w-0 items-center rounded-lg md:h-9",
      active
        ? "bg-sidebar-active text-sidebar-foreground"
        : "text-sidebar-muted hover:bg-hover hover:text-sidebar-foreground",
    );

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
        ref={asideRef}
        id="conversation-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[transform,width] duration-fast md:static md:z-auto",
          rail ? "md:w-sidebar-rail" : "md:w-sidebar",
          open ? "w-sidebar translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
        aria-label="Workspace navigation"
      >
        <div
          className={cn(
            "flex h-12 shrink-0 items-center px-2",
            rail && "md:justify-center",
          )}
        >
          <Link
            href="/app"
            onClick={onClose}
            aria-label="Juris AI workspace"
            className={cn("rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring", rail && "md:hidden")}
          >
            <Logo inverse compact={false} />
          </Link>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="ml-auto size-10 text-sidebar-foreground hover:bg-hover md:hidden"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X className="size-nav-icon" strokeWidth={ICON_STROKE} aria-hidden="true" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="ml-auto hidden size-10 text-sidebar-foreground hover:bg-hover md:inline-flex"
            onClick={onToggleCollapsed}
            aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={rail}
            title={rail ? "Expand sidebar" : "Collapse sidebar"}
          >
            <PanelLeft className="size-4" strokeWidth={ICON_STROKE} aria-hidden="true" />
          </Button>
        </div>

        <div className="shrink-0 space-y-0.5 px-2">
          {WORK_NAV.map((item) => (
            <NavItem
              key={item.id}
              icon={ICONS[item.icon]}
              label={
                item.id === "new-chat" && createConversation.isPending
                  ? "Creating…"
                  : item.label
              }
              href={item.href}
              active={item.match(pathname)}
              collapsed={rail}
              loading={item.id === "new-chat" && createConversation.isPending}
              tone={item.id === "new-chat" ? "primary" : "default"}
              onClick={() => {
                if (item.href) onClose();
                handleWorkItem(item.id);
              }}
            />
          ))}
        </div>

        <section
          aria-label="Pinned"
          className={cn("shrink-0 px-2", rail && "md:hidden")}
        >
          {rail ? (
            <GroupHeader collapsed>Pinned</GroupHeader>
          ) : (
            <GroupHeader>Pinned</GroupHeader>
          )}
          {pinItems.length === 0 ? (
            <p className="px-2.5 py-2 text-xs text-sidebar-muted">
              Pin chats or projects to keep them here.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {pinItems.map((pin, index) => {
                const conversation =
                  pin.type === "conversation"
                    ? conversationById(pin.id)
                    : undefined;
                const project =
                  pin.type === "project"
                    ? projects.data?.find((item) => item.id === pin.id)
                    : undefined;
                const href =
                  pin.type === "conversation"
                    ? `/app/c/${pin.id}`
                    : `/projects/${pin.id}`;
                const label =
                  pin.type === "conversation"
                    ? conversation
                      ? titleOf(conversation)
                      : "Conversation"
                    : (project?.name ?? "Project");
                const active = pathname === href;
                const pinKey = `${pin.type}:${pin.id}`;
                return (
                  <li
                    key={pinKey}
                    draggable
                    onDragStart={() => setDragIndex(index)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => {
                      if (dragIndex === null) return;
                      void reorderPins.mutateAsync(
                        movePin(pinItems, dragIndex, index),
                      );
                      setDragIndex(null);
                    }}
                    className={rowShell(active)}
                  >
                    <Link
                      href={href}
                      onClick={onClose}
                      className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <NavIcon
                        icon={pin.type === "project" ? ICONS.projects : ICONS.pinned}
                        size="nav"
                      />
                      <span className={NAV_LABEL_CLASS}>{label}</span>
                    </Link>
                    <div className="relative w-7 shrink-0">
                      <button
                        type="button"
                        className="grid size-7 place-items-center rounded-lg text-sidebar-muted outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                        aria-label={`Actions for ${label}`}
                        aria-haspopup="menu"
                        onClick={() =>
                          setPinMenuFor((current) =>
                            current === pinKey ? null : pinKey,
                          )
                        }
                      >
                        <Ellipsis
                          className="size-4"
                          strokeWidth={ICON_STROKE}
                          aria-hidden="true"
                        />
                      </button>
                      {pinMenuFor === pinKey ? (
                        <div
                          role="menu"
                          className="absolute right-0 top-full z-40 mt-1 w-44 rounded-lg border border-border bg-surface p-1 shadow-sm"
                        >
                          <MenuItem
                            icon={ICONS.unpin}
                            label="Unpin"
                            onClick={() => {
                              void togglePin.mutateAsync(pin);
                              setPinMenuFor(null);
                            }}
                          />
                          <MenuItem
                            icon={ChevronUp}
                            label="Move up"
                            disabled={index === 0}
                            onClick={() => {
                              void reorderPins.mutateAsync(
                                movePin(pinItems, index, index - 1),
                              );
                              setPinMenuFor(null);
                            }}
                          />
                          <MenuItem
                            icon={ChevronDown}
                            label="Move down"
                            disabled={index === pinItems.length - 1}
                            onClick={() => {
                              void reorderPins.mutateAsync(
                                movePin(pinItems, index, index + 1),
                              );
                              setPinMenuFor(null);
                            }}
                          />
                        </div>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <div className={cn("shrink-0 px-2", rail && "md:hidden")}>
          <button
            type="button"
            className="flex h-9 w-full items-center justify-between rounded-lg pr-2.5 pl-10 text-xs font-medium text-sidebar-muted outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring"
            aria-expanded={projectsOpen}
            onClick={() => setProjectsOpen((value) => !value)}
          >
            Projects
            <ChevronDown
              className={cn("size-4 transition-transform", !projectsOpen && "-rotate-90")}
              strokeWidth={ICON_STROKE}
              aria-hidden="true"
            />
          </button>
          {projectsOpen ? (
            <div className="space-y-0.5">
              <NavItem
                icon={ICONS.projects}
                label="All projects"
                href="/projects"
                active={pathname === "/projects"}
                onClick={onClose}
              />
              {recent.map((project) => (
                <NavItem
                  key={project.id}
                  icon={ICONS.projects}
                  label={project.name}
                  href={`/projects/${project.id}`}
                  active={pathname === `/projects/${project.id}`}
                  onClick={onClose}
                />
              ))}
            </div>
          ) : null}
        </div>

        <nav
          className={cn(
            "min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-2 pb-2",
            rail && "md:hidden",
          )}
          aria-label="Recents"
        >
          {rail ? null : <GroupHeader>Recents</GroupHeader>}
          {conversations.isPending ? (
            <ConversationListSkeleton />
          ) : conversations.isError && !conversations.data ? (
            <div className="mx-1 rounded-lg border border-danger/35 bg-danger/10 px-4 py-5 text-center">
              <p className="text-sm font-medium">Could not load conversations</p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => conversations.refetch()}
              >
                <RefreshCw className="size-4" strokeWidth={ICON_STROKE} aria-hidden="true" />
                Retry
              </Button>
            </div>
          ) : loaded.length === 0 ? (
            <div className="flex flex-col items-center px-2.5 py-7 text-center">
              <NavIcon icon={ICONS.chats} size="nav" />
              <p className="mt-3 text-sm font-medium">No threads yet</p>
              <p className="mt-1 text-xs leading-5 text-sidebar-muted">
                Start your first research thread.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {grouped.map((bucket) => (
                <div key={bucket.group}>
                  <p className="flex h-9 items-center pr-2.5 pl-10 text-xs font-medium text-sidebar-muted">
                    {bucket.label}
                  </p>
                  <div className="space-y-0.5">
                    {bucket.items.map((conversation) => {
                      const href = `/app/c/${conversation.id}`;
                      const active = pathname === href;
                      const pinTarget: PinItem = {
                        type: "conversation",
                        id: conversation.id,
                      };
                      const pinned = isPinned(pinItems, pinTarget);
                      return (
                        <div key={conversation.id} className={rowShell(active)}>
                          <Link
                            href={href}
                            onClick={onClose}
                            aria-current={active ? "page" : undefined}
                            className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <NavIcon icon={ICONS.chats} size="nav" />
                            <span className={NAV_LABEL_CLASS}>
                              {titleOf(conversation)}
                            </span>
                          </Link>
                          <div className="relative w-7 shrink-0">
                            <button
                              type="button"
                              className="grid size-7 place-items-center rounded-lg text-sidebar-muted outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                              aria-label={`Actions for ${titleOf(conversation)}`}
                              aria-haspopup="menu"
                              onClick={() =>
                                setMenuFor((current) =>
                                  current === conversation.id
                                    ? null
                                    : conversation.id,
                                )
                              }
                            >
                              <Ellipsis
                                className="size-4"
                                strokeWidth={ICON_STROKE}
                                aria-hidden="true"
                              />
                            </button>
                            <ConversationRowMenu
                              open={menuFor === conversation.id}
                              onClose={() => setMenuFor(null)}
                              pinned={pinned}
                              onPin={() => {
                                void togglePin.mutateAsync(pinTarget);
                                setMenuFor(null);
                              }}
                              onRename={() => {
                                setRenameTarget(conversation);
                                setRenameValue(titleOf(conversation));
                                setMenuFor(null);
                              }}
                              onDelete={() => {
                                setArchiveTarget(conversation);
                                setMenuFor(null);
                              }}
                              onMove={() => {
                                setMoveTarget(conversation);
                                setMoveProjectId(recent[0]?.id ?? "");
                                setMenuFor(null);
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

              {conversations.hasNextPage ? (
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
                      className="size-4 animate-spin"
                      strokeWidth={ICON_STROKE}
                      aria-hidden="true"
                    />
                  ) : null}
                  {conversations.isFetchingNextPage ? "Loading…" : "Load more"}
                </Button>
              ) : null}
            </div>
          )}
        </nav>

        <div className={cn("shrink-0 border-t border-sidebar-border p-2", rail && "md:px-1")}>
          <ProfileMenu
            user={user}
            loading={userLoading}
            compact={rail}
            capabilities={defaultCapabilities()}
          />
        </div>
      </aside>

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setArchiveTarget(null);
        }}
        title="Delete this conversation?"
        description="It will leave your sidebar. You cannot reopen it in this version."
        confirmLabel="Delete"
        loading={archiveConversation.isPending}
        onConfirm={archiveSelected}
      />

      {renameTarget ? (
        <dialog
          open
          className="m-auto w-[min(92vw,400px)] rounded-lg border border-border bg-surface p-5 text-foreground backdrop:bg-foreground/55"
          onClose={() => setRenameTarget(null)}
        >
          <h2 className="text-lg font-semibold">Rename chat</h2>
          <form
            className="mt-4 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const next = renameValue.trim();
              if (next) {
                void setTitle
                  .mutateAsync({ id: renameTarget.id, title: next })
                  .then(() => {
                    toast.success("Chat renamed on this device.");
                    setRenameTarget(null);
                  })
                  .catch((error: unknown) =>
                    toast.error(
                      error instanceof Error ? error.message : "Could not rename.",
                    ),
                  );
              }
            }}
          >
            <Input
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              aria-label="Conversation title"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setRenameTarget(null)}>
                Cancel
              </Button>
              <Button type="submit">Save</Button>
            </div>
          </form>
        </dialog>
      ) : null}

      {moveTarget ? (
        <dialog
          open
          className="m-auto w-[min(92vw,400px)] rounded-lg border border-border bg-surface p-5 text-foreground backdrop:bg-foreground/55"
          onClose={() => setMoveTarget(null)}
        >
          <h2 className="text-lg font-semibold">Move to project</h2>
          {(projects.data ?? []).length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Create a project first.
            </p>
          ) : (
            <form
              className="mt-4 space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (!moveProjectId) return;
                void attachToProject
                  .mutateAsync({
                    projectId: moveProjectId,
                    conversationId: moveTarget.id,
                  })
                  .then(() => {
                    toast.success("Moved to project.");
                    setMoveTarget(null);
                  })
                  .catch((error: unknown) =>
                    toast.error(
                      error instanceof Error ? error.message : "Could not move.",
                    ),
                  );
              }}
            >
              <select
                className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm"
                value={moveProjectId}
                onChange={(event) => setMoveProjectId(event.target.value)}
                aria-label="Project"
              >
                {(projects.data ?? []).map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setMoveTarget(null)}>
                  Cancel
                </Button>
                <Button type="submit">Move</Button>
              </div>
            </form>
          )}
        </dialog>
      ) : null}
    </>
  );
}
