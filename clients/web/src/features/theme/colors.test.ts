import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("../..", import.meta.url));
const HEX = /#[0-9A-Fa-f]{3,8}\b/u;
const PALETTE_TAILWIND =
  /\b(?:bg|text|border|from|to|via|fill|stroke|ring)-(?:white|black|slate|gray|zinc|neutral|stone)-\d+\b/u;
const ALLOWED = new Set(["config/theme.ts"]);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      out.push(...walk(path));
    } else if (/\.(?:ts|tsx|css)$/u.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx")) {
      out.push(path);
    }
  }
  return out;
}

describe("hardcoded color audit", () => {
  it("keeps hex and palette utilities out of components", () => {
    const hits: string[] = [];
    for (const file of walk(SRC)) {
      const rel = file.slice(SRC.length).replace(/^\//u, "");
      if (ALLOWED.has(rel) || rel.endsWith("styles/theme.css")) continue;
      const text = readFileSync(file, "utf8");
      text.split("\n").forEach((line, index) => {
        if (HEX.test(line) || PALETTE_TAILWIND.test(line)) {
          hits.push(`${rel}:${index + 1}:${line.trim()}`);
        }
      });
    }
    expect(hits).toEqual([]);
  });
});
