"use client";

import { useEffect, useRef } from "react";

import { MenuItem } from "@/components/layout/menu-item";
import { ICONS } from "@/config/navigation";
import { cn } from "@/lib/utils";

export function ConversationRowMenu({
  open,
  onClose,
  pinned,
  onPin,
  onRename,
  onDelete,
  onMove,
  align = "right",
}: {
  open: boolean;
  onClose: () => void;
  pinned: boolean;
  onPin: () => void;
  onRename: () => void;
  onDelete: () => void;
  onMove: () => void;
  align?: "left" | "right";
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) onClose();
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={ref}
      role="menu"
      className={cn(
        "absolute top-full z-40 mt-1 w-52 rounded-lg border border-border bg-surface p-1 shadow-sm",
        align === "right" ? "right-0" : "left-0",
      )}
    >
      <MenuItem
        icon={pinned ? ICONS.unpin : ICONS.pinned}
        label={pinned ? "Unpin" : "Pin"}
        onClick={onPin}
      />
      <MenuItem icon={ICONS.rename} label="Rename" onClick={onRename} />
      <MenuItem
        icon={ICONS.moveToProject}
        label="Move to project"
        onClick={onMove}
      />
      <MenuItem
        icon={ICONS.delete}
        label="Delete"
        danger
        onClick={onDelete}
      />
    </div>
  );
}
