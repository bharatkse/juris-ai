import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME,
  generateThemeCss,
  parseThemeMode,
  THEME_BROWSER_COLORS,
  TOKEN_NAMES,
  lightTokens,
  palettes,
} from "@/config/theme";
import { hslChannelsToRgb } from "@/features/theme/contrast";

describe("parseThemeMode", () => {
  it("defaults to light", () => {
    expect(parseThemeMode(undefined)).toBe("light");
    expect(parseThemeMode(null)).toBe("light");
    expect(parseThemeMode("")).toBe("light");
  });

  it("accepts only light and dark", () => {
    expect(parseThemeMode("light")).toBe("light");
    expect(parseThemeMode("dark")).toBe("dark");
  });

  it("falls back on invalid stored values", () => {
    expect(parseThemeMode("system")).toBe("light");
    expect(parseThemeMode("sepia")).toBe("light");
    expect(parseThemeMode("DARK")).toBe("light");
    expect(parseThemeMode("system", "dark")).toBe("dark");
  });
});

describe("default theme env", () => {
  it("is light or dark", () => {
    expect(["light", "dark"]).toContain(DEFAULT_THEME);
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

  it("uses pure white for the light background", () => {
    expect(lightTokens.background).toBe("0 0% 100%");
    expect(hslChannelsToRgb(lightTokens.background)).toEqual([255, 255, 255]);
    expect(THEME_BROWSER_COLORS.light.toLowerCase()).toBe("#ffffff");
  });
});
