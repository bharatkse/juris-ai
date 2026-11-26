"use client";

import type React from "react";

import { cn } from "@/lib/utils";

export function Switch({
  checked,
  onCheckedChange,
  disabled,
  id,
  label,
  className,
  ...props
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  label?: string;
} & Omit<
  React.ButtonHTMLAttributes<HTMLButtonElement>,
  "type" | "role" | "aria-checked" | "onClick"
>) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      {...props}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={cn(
        "relative h-6 w-10 shrink-0 rounded-full border border-border outline-none transition-colors duration-fast focus-visible:ring-2 focus-visible:ring-ring",
        checked ? "bg-primary" : "bg-muted",
        disabled && "opacity-55",
        className,
      )}
      onClick={() => onCheckedChange(!checked)}
    >
      <span
        className={cn(
          "absolute top-0.5 size-5 rounded-full bg-background shadow-sm transition-[left] duration-fast",
          checked ? "left-[18px]" : "left-0.5",
        )}
        aria-hidden="true"
      />
    </button>
  );
}
