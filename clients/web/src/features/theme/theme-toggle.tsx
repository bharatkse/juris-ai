"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

import { DEFAULT_THEME, type ThemeMode } from "@/config/theme";
import { useTheme } from "@/features/theme/provider";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const current: ThemeMode =
    theme === "dark" || theme === "light"
      ? theme
      : resolvedTheme === "dark" || resolvedTheme === "light"
        ? resolvedTheme
        : DEFAULT_THEME;
  const next: ThemeMode = current === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Switch to dark theme" : "Switch to light theme";

  if (!mounted) {
    return (
      <button
        type="button"
        className={cn(
          "inline-flex size-9 items-center justify-center rounded-md text-muted-foreground",
          className,
        )}
        aria-label="Switch theme"
        disabled
      >
        <Sun className="size-4" aria-hidden="true" />
      </button>
    );
  }

  return (
    <button
      type="button"
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors duration-fast hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      aria-label={label}
      aria-pressed={current === "dark"}
      onClick={() => setTheme(next)}
    >
      {current === "dark" ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
    </button>
  );
}
