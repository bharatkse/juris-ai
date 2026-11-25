/**
 * Theme configuration and token palettes.
 *
 * Adding a named theme: add a palette here (tokens + colorScheme), a label in
 * THEME_META, and it appears in ThemeToggle. Brand (primary/accent) is tokens
 * only — no component edits.
 */

export const THEME_STORAGE_KEY = "juris-theme";

export const THEME_MODES = ["light", "dark", "system"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

export const TOKEN_NAMES = [
  "background",
  "foreground",
  "surface",
  "surface-elevated",
  "border",
  "muted",
  "muted-foreground",
  "primary",
  "primary-foreground",
  "accent",
  "accent-foreground",
  "ring",
  "success",
  "success-foreground",
  "warning",
  "warning-foreground",
  "danger",
  "danger-foreground",
  "info",
  "info-foreground",
  "chat-user",
  "chat-user-foreground",
  "chat-assistant",
  "chat-assistant-foreground",
  "code",
  "code-foreground",
  "citation",
  "citation-foreground",
  "sidebar",
  "sidebar-foreground",
  "sidebar-muted",
  "sidebar-border",
  "selection",
  "skeleton",
] as const;

export type TokenName = (typeof TOKEN_NAMES)[number];
export type TokenPalette = Record<TokenName, string>;

export type NamedPalette = {
  colorScheme: "light" | "dark";
  tokens: TokenPalette;
};

/** Light values match the v1 ink/paper/gold primitives. */
export const lightTokens: TokenPalette = {
  background: "40 36% 95%",
  foreground: "215 51% 12%",
  surface: "38 100% 98%",
  "surface-elevated": "38 100% 98%",
  border: "39 27% 86%",
  muted: "40 30% 92%",
  "muted-foreground": "214 25% 32%",
  primary: "43 82% 28%",
  "primary-foreground": "38 100% 98%",
  accent: "43 82% 28%",
  "accent-foreground": "38 100% 98%",
  ring: "43 82% 28%",
  success: "152 45% 28%",
  "success-foreground": "38 100% 98%",
  warning: "43 82% 28%",
  "warning-foreground": "38 100% 98%",
  danger: "0 56% 39%",
  "danger-foreground": "38 100% 98%",
  info: "216 49% 33%",
  "info-foreground": "38 100% 98%",
  "chat-user": "215 51% 12%",
  "chat-user-foreground": "38 100% 98%",
  "chat-assistant": "38 100% 98%",
  "chat-assistant-foreground": "216 45% 18%",
  code: "215 51% 12%",
  "code-foreground": "40 36% 95%",
  citation: "45 69% 86%",
  "citation-foreground": "216 45% 18%",
  sidebar: "215 51% 12%",
  "sidebar-foreground": "38 100% 98%",
  "sidebar-muted": "214 17% 72%",
  "sidebar-border": "215 28% 22%",
  selection: "45 69% 86%",
  skeleton: "39 20% 88%",
};

/** Soft navy surfaces — not pure black. Gold is lifted for contrast. */
export const darkTokens: TokenPalette = {
  background: "215 28% 9%",
  foreground: "40 36% 95%",
  surface: "215 26% 12%",
  "surface-elevated": "215 24% 16%",
  border: "215 16% 24%",
  muted: "215 20% 15%",
  "muted-foreground": "214 18% 72%",
  primary: "43 78% 56%",
  "primary-foreground": "215 51% 10%",
  accent: "43 78% 56%",
  "accent-foreground": "215 51% 10%",
  ring: "43 78% 56%",
  success: "152 38% 58%",
  "success-foreground": "215 40% 8%",
  warning: "43 78% 56%",
  "warning-foreground": "215 51% 10%",
  danger: "0 58% 68%",
  "danger-foreground": "215 40% 8%",
  info: "214 55% 72%",
  "info-foreground": "215 40% 8%",
  "chat-user": "215 24% 18%",
  "chat-user-foreground": "40 36% 95%",
  "chat-assistant": "215 24% 16%",
  "chat-assistant-foreground": "40 30% 92%",
  code: "215 32% 7%",
  "code-foreground": "40 20% 90%",
  citation: "43 40% 20%",
  "citation-foreground": "43 80% 82%",
  sidebar: "215 32% 7%",
  "sidebar-foreground": "40 36% 95%",
  "sidebar-muted": "214 16% 70%",
  "sidebar-border": "215 18% 18%",
  selection: "43 40% 24%",
  skeleton: "215 16% 20%",
};

/** Named palettes (not including `system`, which follows the OS). */
export const palettes = {
  light: { colorScheme: "light", tokens: lightTokens },
  dark: { colorScheme: "dark", tokens: darkTokens },
} as const satisfies Record<string, NamedPalette>;

export type NamedTheme = keyof typeof palettes;

export const THEME_META: Record<ThemeMode | NamedTheme, { label: string }> = {
  light: { label: "Light" },
  dark: { label: "Dark" },
  system: { label: "System" },
};

export function parseThemeMode(
  value: string | undefined | null,
  fallback: ThemeMode = "system",
): ThemeMode {
  if (value && (THEME_MODES as readonly string[]).includes(value)) {
    return value as ThemeMode;
  }
  return fallback;
}

export const DEFAULT_THEME: ThemeMode = parseThemeMode(
  process.env.NEXT_PUBLIC_DEFAULT_THEME,
  "system",
);

export const NAMED_THEMES = Object.keys(palettes) as NamedTheme[];

export function generateThemeCss(
  all: Record<string, NamedPalette> = palettes,
): string {
  return Object.entries(all)
    .map(([name, palette]) => {
      const selector = name === "light" ? ":root,\n.light" : `.${name}`;
      const decls = TOKEN_NAMES.map(
        (key) => `  --${key}: ${palette.tokens[key]};`,
      ).join("\n");
      return `${selector} {\n  color-scheme: ${palette.colorScheme};\n${decls}\n}`;
    })
    .join("\n\n");
}
