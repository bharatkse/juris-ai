"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { NavIcon } from "@/components/layout/nav-item";
import { cn } from "@/lib/utils";

const itemClass =
  "flex h-9 w-full min-w-0 items-center gap-2.5 rounded-lg px-2.5 text-sm outline-none hover:bg-hover focus-visible:bg-hover focus-visible:ring-2 focus-visible:ring-ring";

export function MenuItem({
  icon,
  label,
  href,
  onClick,
  danger = false,
  trailing,
  disabled = false,
  menuItem = true,
}: {
  icon: LucideIcon;
  label: string;
  href?: string;
  onClick?: () => void;
  danger?: boolean;
  trailing?: ReactNode;
  disabled?: boolean;
  menuItem?: boolean;
}) {
  const classes = cn(itemClass, danger && "text-danger", disabled && "opacity-60");
  const content = (
    <>
      <NavIcon icon={icon} size="menu" />
      <span className="min-w-0 flex-1 truncate text-left">{label}</span>
      {trailing ? (
        <span className="ml-auto shrink-0 text-xs text-muted-foreground">
          {trailing}
        </span>
      ) : null}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        role={menuItem ? "menuitem" : undefined}
        data-profile-menu-item={menuItem ? "true" : undefined}
        className={classes}
        onClick={onClick}
      >
        {content}
      </Link>
    );
  }

  return (
    <button
      type="button"
      role={menuItem ? "menuitem" : undefined}
      data-profile-menu-item={menuItem ? "true" : undefined}
      className={classes}
      disabled={disabled}
      onClick={onClick}
    >
      {content}
    </button>
  );
}
