import { describe, expect, it } from "vitest";

import { palettes } from "@/config/theme";
import { auditAllPalettes, contrastRatio } from "@/features/theme/contrast";

describe("theme contrast (WCAG AA)", () => {
  it("passes text and control pairs in every named palette", () => {
    const violations = auditAllPalettes();
    expect(
      violations.map(
        (row) =>
          `${row.theme} ${row.fg}/${row.bg} ${row.ratio.toFixed(2)} < ${row.min} (${row.usage})`,
      ),
    ).toEqual([]);
  });

  it("uses pure white for the light canvas", () => {
    expect(palettes.light.tokens.background).toBe("0 0% 100%");
  });

  it("uses a soft dark surface, not pure black", () => {
    const [h, s, l] = palettes.dark.tokens.background
      .split(/\s+/u)
      .map((part) => Number.parseFloat(part));
    expect(l).toBeGreaterThan(6);
    expect(l).toBeLessThan(14);
    expect(s).toBeGreaterThan(10);
    expect(h).toBeGreaterThan(200);
  });

  it("computes a known contrast ratio", () => {
    const ratio = contrastRatio("0 0% 0%", "0 0% 100%");
    expect(ratio).toBeCloseTo(21, 0);
  });
});
