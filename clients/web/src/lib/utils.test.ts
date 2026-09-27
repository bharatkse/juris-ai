import { describe, expect, it } from "vitest";

import { cn, getInitials, getSafeNextPath } from "@/lib/utils";

describe("getSafeNextPath", () => {
  it("keeps authenticated app destinations", () => {
    expect(getSafeNextPath("/app/c/conv_123?source=login")).toBe(
      "/app/c/conv_123?source=login",
    );
  });

  it.each([
    "https://attacker.example/app",
    "//attacker.example/app",
    "/login",
    "/app\\@attacker.example",
    null,
  ])("rejects an unsafe destination: %s", (destination) => {
    expect(getSafeNextPath(destination)).toBe("/app");
  });
});

describe("utility helpers", () => {
  it("merges conflicting Tailwind classes", () => {
    expect(cn("px-2 text-sm", false, "px-4")).toBe("text-sm px-4");
  });

  it("builds initials with an email fallback", () => {
    expect(getInitials("Amit", "Vishvakarma", "amit@example.com")).toBe("AV");
    expect(getInitials(null, null, "jurist@example.com")).toBe("J");
  });
});
