import { describe, expect, it } from "vitest";

import { isPinned, movePin, togglePin, type PinItem } from "@/features/pins/order";

const items: PinItem[] = [
  { type: "conversation", id: "c1" },
  { type: "project", id: "p1" },
  { type: "conversation", id: "c2" },
];

describe("pin ordering", () => {
  it("moves an item and no-ops out of range", () => {
    expect(movePin(items, 0, 2).map((item) => item.id)).toEqual([
      "p1",
      "c2",
      "c1",
    ]);
    expect(movePin(items, -1, 1)).toEqual(items);
  });

  it("toggles pin membership", () => {
    const next = togglePin(items, { type: "conversation", id: "c1" });
    expect(isPinned(next, { type: "conversation", id: "c1" })).toBe(false);
    expect(
      isPinned(togglePin(next, { type: "conversation", id: "c1" }), {
        type: "conversation",
        id: "c1",
      }),
    ).toBe(true);
  });
});
