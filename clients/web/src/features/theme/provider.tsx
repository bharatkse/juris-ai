"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

import {
  DEFAULT_THEME,
  NAMED_THEMES,
  THEME_STORAGE_KEY,
} from "@/config/theme";
import { migrateStoredTheme } from "@/features/theme/storage";

function migrateLegacyTheme(): void {
  try {
    migrateStoredTheme(globalThis.localStorage, DEFAULT_THEME);
  } catch {
    /* private mode / blocked storage */
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  if (typeof window !== "undefined") {
    migrateLegacyTheme();
  }

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme={DEFAULT_THEME}
      enableSystem={false}
      disableTransitionOnChange
      storageKey={THEME_STORAGE_KEY}
      themes={[...NAMED_THEMES]}
    >
      {children}
    </NextThemesProvider>
  );
}

export { useTheme } from "next-themes";
