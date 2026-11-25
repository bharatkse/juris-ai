import { afterEach, describe, expect, it } from "vitest";

import { THEME_STORAGE_KEY } from "@/config/theme";
import { readStoredTheme, writeStoredTheme } from "@/features/theme/storage";

describe("theme storage", () => {
  afterEach(() => {
    try {
      globalThis.localStorage?.removeItem(THEME_STORAGE_KEY);
    } catch {
      /* ignore */
    }
  });

  it("returns null when nothing is stored", () => {
    const memory = new Map<string, string>();
    expect(
      readStoredTheme({ getItem: (key) => memory.get(key) ?? null }),
    ).toBeNull();
  });

  it("persists a valid preference", () => {
    const memory = new Map<string, string>();
    expect(
      writeStoredTheme("dark", {
        setItem: (key, value) => {
          memory.set(key, value);
        },
      }),
    ).toBe(true);
    expect(
      readStoredTheme({ getItem: (key) => memory.get(key) ?? null }),
    ).toBe("dark");
  });

  it("ignores invalid stored values", () => {
    expect(
      readStoredTheme({ getItem: () => "high-contrast-please" }),
    ).toBeNull();
  });

  it("does not throw when storage is unavailable", () => {
    expect(readStoredTheme(null)).toBeNull();
    expect(writeStoredTheme("light", null)).toBe(false);
  });
});
