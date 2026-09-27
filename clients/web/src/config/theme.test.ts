import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME,
  generateThemeCss,
  parseThemeMode,
  TOKEN_NAMES,
  palettes,
} from "@/config/theme";

describe("parseThemeMode", () => {
  it("defaults to system", () => {
    expect(parseThemeMode(undefined)).toBe("system");
    expect(parseThemeMode(null)).toBe("system");
    expect(parseThemeMode("")).toBe("system");
  });

  it("accepts light, dark, and system", () => {
    expect(parseThemeMode("light")).toBe("light");
    expect(parseThemeMode("dark")).toBe("dark");
    expect(parseThemeMode("system")).toBe("system");
  });

  it("falls back on invalid stored values", () => {
    expect(parseThemeMode("sepia")).toBe("system");
    expect(parseThemeMode("DARK")).toBe("system");
  });
});

describe("default theme env", () => {
  it("is a valid mode (system unless NEXT_PUBLIC_DEFAULT_THEME is set)", () => {
    expect(["light", "dark", "system"]).toContain(DEFAULT_THEME);
  });
});

describe("token palettes", () => {
  it("defines every semantic token for each named theme", () => {
    for (const [name, palette] of Object.entries(palettes)) {
      for (const token of TOKEN_NAMES) {
        expect(palette.tokens[token], `${name}.${token}`).toMatch(
          /^[\d.]+ [\d.]+% [\d.]+%$/u,
        );
      }
    }
  });

  it("keeps src/styles/theme.css in sync with generateThemeCss()", () => {
    const cssPath = fileURLToPath(
      new URL("../styles/theme.css", import.meta.url),
    );
    const file = readFileSync(cssPath, "utf8");
    const generated = generateThemeCss();
    expect(file).toContain(generated);
  });
});
