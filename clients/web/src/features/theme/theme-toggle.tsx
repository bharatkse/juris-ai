"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

import { THEME_META, THEME_MODES, type ThemeMode } from "@/config/theme";
import { useTheme } from "@/features/theme/provider";
import { cn } from "@/lib/utils";

const ICONS = {
  light: Sun,
  dark: Moon,
  system: Monitor,
} as const;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        className={cn(
          "h-9 w-[9.5rem] rounded-md border border-border bg-surface",
          className,
        )}
        aria-hidden="true"
      />
    );
  }

  const current = (THEME_MODES as readonly string[]).includes(theme ?? "")
    ? (theme as ThemeMode)
    : "system";

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className={cn(
        "inline-flex rounded-md border border-border bg-surface p-0.5",
        className,
      )}
    >
      {THEME_MODES.map((mode) => {
        const Icon = ICONS[mode];
        const selected = current === mode;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={THEME_META[mode].label}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-sm px-2.5 text-xs font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
              selected
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setTheme(mode)}
          >
            <Icon className="size-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">{THEME_META[mode].label}</span>
          </button>
        );
      })}
    </div>
  );
}
