import { describe, expect, it } from "vitest";

import { buildChatFormData } from "@/lib/api/chat";

describe("buildChatFormData", () => {
  it("uses repeated multipart file fields without a manual content type", () => {
    const files = [
      new File(["first"], "first.txt", { type: "text/plain" }),
      new File(["second"], "second.md", { type: "text/markdown" }),
    ];

    const form = buildChatFormData({
      conversationId: "conv_123",
      message: "Review these documents",
      files,
    });

    expect(form.get("conversation_id")).toBe("conv_123");
    expect(form.get("message")).toBe("Review these documents");
    expect(form.getAll("files")).toEqual(files);
  });
});
