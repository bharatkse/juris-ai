"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";

import { MenuItem } from "@/components/layout/menu-item";
import { NavIcon } from "@/components/layout/nav-item";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ICON_STROKE, ICONS, profileMenuItems } from "@/config/navigation";
import {
  defaultCapabilities,
  type Capabilities,
} from "@/features/auth/capabilities";
import { currentUserQueryKey } from "@/features/auth/use-current-user";
import { useTheme } from "@/features/theme/provider";
import { clearLocalUserData } from "@/features/workspace/clear-local";
import { apiFetch } from "@/lib/api/client";
import { cn, getInitials } from "@/lib/utils";
import type { User } from "@/types/api";

const ITEM_SELECTOR = "[data-profile-menu-item='true']";

export function ProfileMenu({
  user,
  loading = false,
  compact = false,
  capabilities = defaultCapabilities(),
}: {
  user?: User;
  loading?: boolean;
  compact?: boolean;
  capabilities?: Capabilities;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const items = useMemo(() => profileMenuItems(capabilities), [capabilities]);

  const logout = useMutation({
    mutationFn: () =>
      apiFetch<{ authenticated: boolean }>("/api/auth/logout", {
        method: "POST",
      }),
    onSuccess: () => {
      clearLocalUserData(user?.id);
      queryClient.removeQueries({ queryKey: currentUserQueryKey });
      router.replace("/login");
      router.refresh();
    },
    onError: () => toast.error("Could not log out. Please try again."),
  });

  const currentTheme =
    theme === "dark" || theme === "light"
      ? theme
      : resolvedTheme === "dark" || resolvedTheme === "light"
        ? resolvedTheme
        : "light";

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
        return;
      }
      const focusable = menuItems();
      if (focusable.length === 0) return;
      const index = focusable.indexOf(document.activeElement as HTMLElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        const next = focusable[(index + 1 + focusable.length) % focusable.length];
        next?.focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        const next = focusable[(index - 1 + focusable.length) % focusable.length];
        next?.focus();
      } else if (event.key === "Home") {
        event.preventDefault();
        focusable[0]?.focus();
      } else if (event.key === "End") {
        event.preventDefault();
        focusable[focusable.length - 1]?.focus();
      } else if (event.key === "Tab") {
        event.preventDefault();
        if (event.shiftKey) {
          focusable[(index - 1 + focusable.length) % focusable.length]?.focus();
        } else {
          focusable[(index + 1) % focusable.length]?.focus();
        }
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    menuItems()[0]?.focus();
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function menuItems(): HTMLElement[] {
    return Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>(ITEM_SELECTOR) ?? [],
    );
  }

  if (loading) {
    return (
      <div className="flex h-10 items-center gap-2.5 px-2.5" aria-label="Loading account">
        <Skeleton className="size-8 shrink-0 rounded-full" />
        <div className={cn("flex-1 space-y-2", compact && "md:hidden")}>
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-2.5 w-32" />
        </div>
      </div>
    );
  }

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.email ||
    "Juris user";

  const groups = ["account", "workspace", "system", "session"] as const;

  return (
    <div className="relative" ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={cn(
          "group/nav flex h-10 w-full items-center gap-2.5 rounded-lg px-2.5 text-sidebar-foreground outline-none transition-colors hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring md:h-9",
          compact && "md:size-10 md:justify-center md:px-0",
        )}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={displayName}
        title={compact ? displayName : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="grid size-8 shrink-0 place-items-center rounded-full border border-sidebar-border bg-hover text-xs font-semibold">
          {getInitials(user?.first_name, user?.last_name, user?.email)}
        </span>
        <span className={cn("min-w-0 flex-1 text-left", compact && "md:hidden")}>
          <span className="block truncate text-sm font-medium leading-5">
            {displayName}
          </span>
          <span className="block truncate text-xs leading-4 text-sidebar-muted">
            {user?.email ?? "Signed in"}
          </span>
        </span>
        <ChevronRight
          className={cn(
            "size-4 shrink-0 text-sidebar-muted",
            compact && "md:hidden",
          )}
          strokeWidth={ICON_STROKE}
          aria-hidden="true"
        />
        {compact ? (
          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 hidden -translate-y-1/2 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground opacity-0 shadow-sm transition-opacity delay-300 duration-fast group-hover/nav:opacity-100 md:block">
            {displayName}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label="Account"
          className="absolute bottom-full left-0 right-0 z-50 mb-2 rounded-lg border border-border bg-surface p-1 text-foreground shadow-sm"
        >
          <div className="border-b border-border px-2.5 py-2">
            <p className="truncate text-sm font-medium">{displayName}</p>
            {user?.email ? (
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            ) : null}
          </div>
          {groups.map((group) => {
            const grouped = items.filter((item) => item.group === group);
            if (grouped.length === 0) return null;
            return (
              <div
                key={group}
                className="border-b border-border py-1 last:border-b-0"
              >
                {grouped.map((item) => {
                  if (item.kind === "appearance") {
                    const AppearanceIcon =
                      currentTheme === "dark"
                        ? ICONS.appearanceDark
                        : ICONS.appearanceLight;
                    return (
                      <div
                        key={item.id}
                        className="flex h-9 items-center gap-2.5 rounded-lg px-2.5"
                      >
                        <NavIcon icon={AppearanceIcon} size="menu" />
                        <span className="min-w-0 flex-1 truncate text-sm">
                          {item.label}
                        </span>
                        <Switch
                          checked={currentTheme === "dark"}
                          label="Dark theme"
                          data-profile-menu-item="true"
                          onCheckedChange={(checked) =>
                            setTheme(checked ? "dark" : "light")
                          }
                        />
                      </div>
                    );
                  }
                  if (item.kind === "signout") {
                    return (
                      <MenuItem
                        key={item.id}
                        icon={ICONS[item.icon]}
                        label={logout.isPending ? "Signing out…" : item.label}
                        disabled={logout.isPending}
                        onClick={() => logout.mutate()}
                      />
                    );
                  }
                  return (
                    <MenuItem
                      key={item.id}
                      icon={ICONS[item.icon]}
                      label={item.label}
                      href={item.href}
                      onClick={() => setOpen(false)}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
