import { afterEach, describe, expect, it } from "vitest";

import { THEME_STORAGE_KEY } from "@/config/theme";
import {
  migrateStoredTheme,
  readStoredTheme,
  writeStoredTheme,
} from "@/features/theme/storage";

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

  it("migrates system and unknown values to the fallback", () => {
    const memory = new Map<string, string>([[THEME_STORAGE_KEY, "system"]]);
    const storage = {
      getItem: (key: string) => memory.get(key) ?? null,
      setItem: (key: string, value: string) => {
        memory.set(key, value);
      },
      removeItem: (key: string) => {
        memory.delete(key);
      },
    };
    expect(migrateStoredTheme(storage, "light")).toBe("light");
    expect(memory.get(THEME_STORAGE_KEY)).toBe("light");

    memory.set(THEME_STORAGE_KEY, "high-contrast");
    expect(migrateStoredTheme(storage, "dark")).toBe("dark");
    expect(memory.get(THEME_STORAGE_KEY)).toBe("dark");
  });
});
