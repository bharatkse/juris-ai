"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

import {
  DEFAULT_THEME,
  NAMED_THEMES,
  THEME_STORAGE_KEY,
} from "@/config/theme";
import { readStoredTheme } from "@/features/theme/storage";

function discardInvalidStoredTheme(): void {
  try {
    const raw = globalThis.localStorage?.getItem(THEME_STORAGE_KEY);
    if (raw && readStoredTheme() === null) {
      globalThis.localStorage.removeItem(THEME_STORAGE_KEY);
    }
  } catch {
    /* private mode / blocked storage */
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  if (typeof window !== "undefined") {
    discardInvalidStoredTheme();
  }

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme={DEFAULT_THEME}
      enableSystem
      disableTransitionOnChange
      storageKey={THEME_STORAGE_KEY}
      themes={[...NAMED_THEMES]}
    >
      {children}
    </NextThemesProvider>
  );
}

export { useTheme } from "next-themes";
