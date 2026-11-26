"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderKanban, MessageSquareText, Plus, Settings } from "lucide-react";

import { flattenConversations, useConversations } from "@/features/conversations/queries";
import { useProjects } from "@/features/projects/queries";
import { displayTitle, useConversationTitles } from "@/features/titles/queries";
import { cn } from "@/lib/utils";

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const conversations = useConversations();
  const projects = useProjects();
  const titles = useConversationTitles();
  const loaded = flattenConversations(conversations.data);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const q = query.trim().toLocaleLowerCase();
  const chatHits = useMemo(
    () =>
      loaded
        .map((conversation) => ({
          ...conversation,
          label: displayTitle(
            conversation.id,
            conversation.title,
            titles.data,
          ),
        }))
        .filter((conversation) =>
          q ? conversation.label.toLocaleLowerCase().includes(q) : true,
        )
        .slice(0, 8),
    [loaded, q, titles.data],
  );
  const projectHits = useMemo(
    () =>
      (projects.data ?? [])
        .filter((project) =>
          q ? project.name.toLocaleLowerCase().includes(q) : true,
        )
        .slice(0, 6),
    [projects.data, q],
  );

  if (!open) return null;

  function go(href: string) {
    onClose();
    router.push(href);
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[15vh]">
      <button
        type="button"
        className="absolute inset-0 bg-foreground/40"
        aria-label="Close search"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-label="Search"
        className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-surface shadow-sm"
      >
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") onClose();
          }}
          placeholder="Search chats, projects, and actions"
          className="h-12 w-full border-b border-border bg-transparent px-4 text-sm outline-none"
          aria-label="Search workspace"
        />
        <div className="max-h-80 overflow-y-auto p-1.5">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-hover"
            onClick={() => go("/app")}
          >
            <Plus className="size-4" aria-hidden="true" />
            New chat
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-hover"
            onClick={() => go("/settings/general")}
          >
            <Settings className="size-4" aria-hidden="true" />
            Settings
          </button>
          {projectHits.length ? (
            <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Projects
            </p>
          ) : null}
          {projectHits.map((project) => (
            <button
              key={project.id}
              type="button"
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-hover",
              )}
              onClick={() => go(`/projects/${project.id}`)}
            >
              <FolderKanban className="size-4" aria-hidden="true" />
              <span className="truncate">{project.name}</span>
            </button>
          ))}
          {chatHits.length ? (
            <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Chats
            </p>
          ) : null}
          {chatHits.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-hover"
              onClick={() => go(`/app/c/${conversation.id}`)}
            >
              <MessageSquareText className="size-4" aria-hidden="true" />
              <span className="truncate">{conversation.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
