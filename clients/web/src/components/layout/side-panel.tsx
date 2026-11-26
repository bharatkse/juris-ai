"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

const MIN_WIDTH = 280;
const MAX_WIDTH = 560;
const DEFAULT_WIDTH = 360;

export function SidePanel({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const dragging = useRef(false);

  useEffect(() => {
    function onMove(event: MouseEvent) {
      if (!dragging.current) return;
      const next = window.innerWidth - event.clientX;
      setWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next)));
    }
    function onUp() {
      dragging.current = false;
      document.body.style.cursor = "";
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  if (!open) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        aria-label="Dismiss panel"
        className="fixed inset-0 z-[60] bg-foreground/40 md:hidden"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-label={title}
        className="fixed inset-0 z-[70] flex w-full bg-background md:relative md:inset-auto md:z-auto md:h-full md:w-[var(--panel-w)] md:shrink-0 md:border-l md:border-border"
        style={{ ["--panel-w" as string]: `${width}px` }}
      >
        <div
          className="hidden w-1 shrink-0 cursor-col-resize hover:bg-border md:block"
          aria-hidden="true"
          onMouseDown={(event) => {
            event.preventDefault();
            dragging.current = true;
            document.body.style.cursor = "col-resize";
          }}
        />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="flex h-12 shrink-0 items-center justify-between px-4">
            <h2 className="text-sm font-semibold">{title}</h2>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Close panel"
              onClick={onClose}
            >
              <X className="size-4" aria-hidden="true" />
            </Button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">{children}</div>
        </div>
      </aside>
    </>
  );
}
