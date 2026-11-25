/**
 * Theme configuration. Only light and dark. Light page canvas is pure white.
 */

export const THEME_STORAGE_KEY = "juris-theme";

export const THEME_MODES = ["light", "dark"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

export const TOKEN_NAMES = [
  "background",
  "foreground",
  "surface",
  "surface-elevated",
  "hover",
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

/** Browser chrome (theme-color meta). Light canvas is #FFFFFF. */
export const THEME_BROWSER_COLORS = {
  light: "#FFFFFF",
  dark: "#16191F",
} as const;

/** Light: #FFFFFF canvas, #F9FAFB sidebar/hover, near-black text. */
export const lightTokens: TokenPalette = {
  background: "0 0% 100%",
  foreground: "222 47% 11%",
  surface: "0 0% 100%",
  "surface-elevated": "0 0% 100%",
  hover: "210 20% 98%",
  border: "220 13% 91%",
  muted: "210 20% 98%",
  "muted-foreground": "220 9% 32%",
  primary: "43 82% 28%",
  "primary-foreground": "0 0% 100%",
  accent: "43 82% 28%",
  "accent-foreground": "0 0% 100%",
  ring: "43 82% 28%",
  success: "152 45% 28%",
  "success-foreground": "0 0% 100%",
  warning: "43 82% 28%",
  "warning-foreground": "0 0% 100%",
  danger: "0 56% 39%",
  "danger-foreground": "0 0% 100%",
  info: "216 49% 33%",
  "info-foreground": "0 0% 100%",
  "chat-user": "210 20% 98%",
  "chat-user-foreground": "222 47% 11%",
  "chat-assistant": "0 0% 100%",
  "chat-assistant-foreground": "222 47% 11%",
  code: "222 20% 14%",
  "code-foreground": "0 0% 98%",
  citation: "43 55% 92%",
  "citation-foreground": "222 47% 11%",
  sidebar: "210 20% 98%",
  "sidebar-foreground": "222 47% 11%",
  "sidebar-muted": "220 9% 32%",
  "sidebar-border": "220 13% 91%",
  selection: "43 55% 90%",
  skeleton: "220 14% 94%",
};

/** Soft dark neutrals — not pure black. */
export const darkTokens: TokenPalette = {
  background: "220 16% 10%",
  foreground: "210 20% 96%",
  surface: "220 14% 12%",
  "surface-elevated": "220 12% 15%",
  hover: "220 12% 16%",
  border: "220 10% 22%",
  muted: "220 12% 16%",
  "muted-foreground": "214 14% 72%",
  primary: "43 78% 56%",
  "primary-foreground": "220 20% 8%",
  accent: "43 78% 56%",
  "accent-foreground": "220 20% 8%",
  ring: "43 78% 56%",
  success: "152 38% 58%",
  "success-foreground": "220 20% 8%",
  warning: "43 78% 56%",
  "warning-foreground": "220 20% 8%",
  danger: "0 58% 68%",
  "danger-foreground": "220 20% 8%",
  info: "214 55% 72%",
  "info-foreground": "220 20% 8%",
  "chat-user": "220 12% 16%",
  "chat-user-foreground": "210 20% 96%",
  "chat-assistant": "220 16% 10%",
  "chat-assistant-foreground": "210 20% 96%",
  code: "220 18% 8%",
  "code-foreground": "210 16% 92%",
  citation: "43 30% 18%",
  "citation-foreground": "43 80% 82%",
  sidebar: "220 16% 8%",
  "sidebar-foreground": "210 20% 96%",
  "sidebar-muted": "214 12% 70%",
  "sidebar-border": "220 10% 18%",
  selection: "43 30% 22%",
  skeleton: "220 10% 18%",
};

export const palettes = {
  light: { colorScheme: "light", tokens: lightTokens },
  dark: { colorScheme: "dark", tokens: darkTokens },
} as const satisfies Record<ThemeMode, NamedPalette>;

export type NamedTheme = keyof typeof palettes;

export const THEME_META: Record<ThemeMode, { label: string }> = {
  light: { label: "Light" },
  dark: { label: "Dark" },
};

export function parseThemeMode(
  value: string | undefined | null,
  fallback: ThemeMode = "light",
): ThemeMode {
  if (value && (THEME_MODES as readonly string[]).includes(value)) {
    return value as ThemeMode;
  }
  return fallback;
}

export const DEFAULT_THEME: ThemeMode = parseThemeMode(
  process.env.NEXT_PUBLIC_DEFAULT_THEME,
  "light",
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
