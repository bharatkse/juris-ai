import { describe, expect, it } from "vitest";

import { parseClientEnv } from "@/config/env";

describe("parseClientEnv", () => {
  it("accepts light and dark default themes", () => {
    expect(parseClientEnv({ NEXT_PUBLIC_DEFAULT_THEME: "light" })).toEqual(
      expect.objectContaining({ NEXT_PUBLIC_DEFAULT_THEME: "light" }),
    );
    expect(parseClientEnv({ NEXT_PUBLIC_DEFAULT_THEME: "dark" })).toEqual(
      expect.objectContaining({ NEXT_PUBLIC_DEFAULT_THEME: "dark" }),
    );
  });

  it("rejects system and other theme values", () => {
    expect(() =>
      parseClientEnv({ NEXT_PUBLIC_DEFAULT_THEME: "system" }),
    ).toThrow();
    expect(() =>
      parseClientEnv({ NEXT_PUBLIC_DEFAULT_THEME: "sepia" }),
    ).toThrow();
  });
});
