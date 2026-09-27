import {
  THEME_MODES,
  THEME_STORAGE_KEY,
  type ThemeMode,
} from "@/config/theme";

export function readStoredTheme(
  storage: Pick<Storage, "getItem"> | null | undefined = globalThis.localStorage,
  key = THEME_STORAGE_KEY,
): ThemeMode | null {
  try {
    const raw = storage?.getItem(key);
    if (raw && (THEME_MODES as readonly string[]).includes(raw)) {
      return raw as ThemeMode;
    }
    return null;
  } catch {
    return null;
  }
}

export function writeStoredTheme(
  value: ThemeMode,
  storage: Pick<Storage, "setItem"> | null | undefined = globalThis.localStorage,
  key = THEME_STORAGE_KEY,
): boolean {
  if (!storage) {
    return false;
  }
  try {
    storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}
