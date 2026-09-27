import { describe, expect, it } from "vitest";

import {
  addValidatedFiles,
  MAX_CHAT_FILE_BYTES,
  validateChatMessage,
} from "@/features/chat/files";

function file(name: string, size = 128, lastModified = 1): File {
  return { name, size, lastModified } as File;
}

describe("addValidatedFiles", () => {
  it("accepts supported extensions case-insensitively", () => {
    const result = addValidatedFiles([], [
      file("brief.PDF"),
      file("contract.docx"),
      file("notes.md"),
    ]);

    expect(result.errors).toEqual([]);
    expect(result.files).toHaveLength(3);
  });

  it("rejects unsupported, oversized, and duplicate files", () => {
    const existing = file("brief.pdf");
    const result = addValidatedFiles([existing], [
      existing,
      file("script.exe"),
      file("record.pdf", MAX_CHAT_FILE_BYTES + 1),
    ]);

    expect(result.files).toEqual([existing]);
    expect(result.errors).toEqual([
      "brief.pdf: this file is already attached.",
      "script.exe: unsupported type. Use PDF, DOCX, TXT, MD, or HTML.",
      "record.pdf: file must be 20 MB or smaller.",
    ]);
  });

  it("enforces the five-file total", () => {
    const result = addValidatedFiles(
      [1, 2, 3, 4].map((index) => file(`${index}.txt`, index)),
      [file("5.txt", 5), file("6.txt", 6)],
    );

    expect(result.files).toHaveLength(5);
    expect(result.errors).toEqual(["You can attach up to 5 files."]);
  });
});

describe("validateChatMessage", () => {
  it("requires non-whitespace content", () => {
    expect(validateChatMessage("   ")).toBe("Enter a message before sending.");
  });

  it("accepts a message at the maximum length", () => {
    expect(validateChatMessage("a".repeat(10_000))).toBeNull();
    expect(validateChatMessage("a".repeat(10_001))).toContain(
      "10,000 characters or fewer",
    );
  });
});
