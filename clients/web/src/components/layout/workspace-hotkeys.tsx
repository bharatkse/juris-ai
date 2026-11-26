"use client";

import { useEffect, useState } from "react";

import { CommandPalette } from "@/components/layout/command-palette";
import { ShortcutsDialog } from "@/components/layout/shortcuts-dialog";

function typingInField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

export const OPEN_SEARCH_EVENT = "juris:open-search";

export function openWorkspaceSearch(): void {
  window.dispatchEvent(new Event(OPEN_SEARCH_EVENT));
}

export function WorkspaceHotkeys() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    function openSearch() {
      setShortcutsOpen(false);
      setSearchOpen(true);
    }
    window.addEventListener(OPEN_SEARCH_EVENT, openSearch);
    return () => window.removeEventListener(OPEN_SEARCH_EVENT, openSearch);
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setShortcutsOpen(false);
        setSearchOpen((open) => !open);
        return;
      }
      if (event.key === "?" && !meta && !typingInField(event.target)) {
        event.preventDefault();
        setSearchOpen(false);
        setShortcutsOpen((open) => !open);
      }
      if (event.key === "Escape") {
        setSearchOpen(false);
        setShortcutsOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      <ShortcutsDialog
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />
    </>
  );
}
