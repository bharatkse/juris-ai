"use client";

import { useEffect, useRef } from "react";
import { TriangleAlert, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  loading = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  loading?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
      className="m-auto w-[min(92vw,440px)] rounded-lg border border-border bg-surface p-0 text-foreground backdrop:bg-foreground/55"
      onCancel={(event) => {
        if (loading) {
          event.preventDefault();
          return;
        }
        onOpenChange(false);
      }}
      onClose={() => {
        if (open) onOpenChange(false);
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !loading) {
          onOpenChange(false);
        }
      }}
    >
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-danger/15 text-danger">
            <TriangleAlert className="size-5" aria-hidden="true" />
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="-mr-2 -mt-2"
            aria-label="Close dialog"
            disabled={loading}
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>
        <h2
          id="confirm-dialog-title"
          className="mt-5 text-lg font-semibold tracking-[-0.01em]"
        >
          {title}
        </h2>
        <p
          id="confirm-dialog-description"
          className="mt-2 text-sm leading-6 text-muted-foreground"
        >
          {description}
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            autoFocus
            disabled={loading}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            loading={loading}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
