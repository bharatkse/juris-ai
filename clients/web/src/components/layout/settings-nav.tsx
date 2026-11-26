"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { NavItem } from "@/components/layout/nav-item";
import {
  ICON_STROKE,
  ICONS,
  isSettingsPathActive,
  visibleSettingsNav,
} from "@/config/navigation";
import { defaultCapabilities } from "@/features/auth/capabilities";

export function SettingsNav() {
  const pathname = usePathname();
  const router = useRouter();
  const items = visibleSettingsNav(defaultCapabilities());

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-border bg-sidebar md:h-dvh md:w-60 md:border-b-0 md:border-r md:border-sidebar-border">
      <div className="px-2 py-4">
        <Link
          href="/app"
          className="inline-flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm text-muted-foreground outline-none hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="size-4" strokeWidth={ICON_STROKE} aria-hidden="true" />
          Back to chat
        </Link>
      </div>
      <nav aria-label="Settings" className="hidden flex-1 space-y-0.5 overflow-y-auto px-2 pb-4 md:block">
        {items.map((item) => (
          <NavItem
            key={item.id}
            icon={ICONS[item.icon]}
            label={item.label}
            href={item.href}
            active={isSettingsPathActive(pathname, item.href)}
          />
        ))}
      </nav>
      <div className="px-4 pb-4 md:hidden">
        <label htmlFor="settings-mobile-nav" className="sr-only">
          Settings section
        </label>
        <select
          id="settings-mobile-nav"
          className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm"
          value={
            items.find((item) => isSettingsPathActive(pathname, item.href))
              ?.href ?? items[0]?.href
          }
          onChange={(event) => router.push(event.target.value)}
        >
          {items.map((item) => (
            <option key={item.id} value={item.href}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
    </aside>
  );
}
