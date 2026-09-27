import { describe, expect, it } from "vitest";

import {
  MESSAGE_VIRTUALIZATION_THRESHOLD,
  shouldVirtualizeMessages,
} from "@/features/chat/virtualization";

describe("message virtualization threshold", () => {
  it("keeps short threads in the simple accessible renderer", () => {
    expect(shouldVirtualizeMessages(MESSAGE_VIRTUALIZATION_THRESHOLD - 1)).toBe(
      false,
    );
  });

  it("virtualizes long histories at the threshold", () => {
    expect(shouldVirtualizeMessages(MESSAGE_VIRTUALIZATION_THRESHOLD)).toBe(
      true,
    );
    expect(shouldVirtualizeMessages(500)).toBe(true);
  });
});
