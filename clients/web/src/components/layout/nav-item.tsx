"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { LoaderCircle } from "lucide-react";

import { ICON_STROKE } from "@/config/navigation";
import { cn } from "@/lib/utils";

export const NAV_ICON_SLOT =
  "nav-icon-slot grid size-5 shrink-0 place-items-center";
export const NAV_LABEL_CLASS = "nav-item-label min-w-0 flex-1 truncate text-left";

export function NavIcon({
  icon: Icon,
  size = "nav",
}: {
  icon: LucideIcon;
  size?: "nav" | "menu";
}) {
  return (
    <span className={NAV_ICON_SLOT} aria-hidden="true">
      <Icon
        className={size === "nav" ? "size-nav-icon" : "size-4"}
        strokeWidth={ICON_STROKE}
      />
    </span>
  );
}

export function GroupHeader({
  children,
  collapsed = false,
}: {
  children: string;
  collapsed?: boolean;
}) {
  if (collapsed) {
    return (
      <div
        className="mx-2 my-1 hidden h-px bg-sidebar-border md:block"
        role="separator"
        aria-hidden="true"
      />
    );
  }
  return (
    <p className="flex h-9 items-center pr-2.5 pl-10 text-xs font-medium text-sidebar-muted">
      {children}
    </p>
  );
}

const rowClass = (active: boolean, collapsed: boolean) =>
  cn(
    "group/nav relative flex h-10 w-full min-w-0 items-center gap-2.5 rounded-lg px-2.5 text-sm outline-none transition-colors duration-fast md:h-9",
    "focus-visible:ring-2 focus-visible:ring-ring",
    collapsed && "md:size-10 md:justify-center md:px-0",
    active
      ? "bg-sidebar-active font-medium text-sidebar-foreground"
      : "font-normal text-sidebar-muted hover:bg-hover hover:text-sidebar-foreground",
  );

export function NavItem({
  icon,
  label,
  href,
  active = false,
  badge,
  collapsed = false,
  onClick,
  loading = false,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  href?: string;
  active?: boolean;
  badge?: string | number;
  collapsed?: boolean;
  onClick?: () => void;
  loading?: boolean;
  tone?: "default" | "primary";
}) {
  const classes = cn(
    rowClass(active, collapsed),
    tone === "primary" &&
      !active &&
      "bg-primary font-medium text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground",
  );

  const body = (
    <>
      {loading ? (
        <span className={NAV_ICON_SLOT} aria-hidden="true">
          <LoaderCircle
            className="size-4 animate-spin"
            strokeWidth={ICON_STROKE}
          />
        </span>
      ) : (
        <NavIcon icon={icon} size="nav" />
      )}
      <span className={cn(NAV_LABEL_CLASS, collapsed && "md:hidden")}>
        {label}
      </span>
      {badge != null && !collapsed ? (
        <span className="shrink-0 text-xs text-sidebar-muted">{badge}</span>
      ) : null}
      {collapsed ? (
        <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 hidden -translate-y-1/2 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground opacity-0 shadow-sm transition-opacity delay-300 duration-fast group-hover/nav:opacity-100 group-focus-visible/nav:opacity-100 md:block">
          {label}
        </span>
      ) : null}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        aria-label={collapsed ? label : undefined}
        title={collapsed ? label : undefined}
        className={classes}
        onClick={onClick}
      >
        {body}
      </Link>
    );
  }

  return (
    <button
      type="button"
      aria-label={label}
      title={collapsed ? label : undefined}
      className={classes}
      disabled={loading}
      onClick={onClick}
    >
      {body}
    </button>
  );
}
