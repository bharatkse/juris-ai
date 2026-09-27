import { describe, expect, it } from "vitest";

import {
  getStarterPrompt,
  STARTER_PROMPTS,
  starterConversationTitle,
} from "@/features/chat/starters";

describe("starter prompts", () => {
  it("exposes the five planner-friendly prompts", () => {
    expect(STARTER_PROMPTS.map((starter) => starter.prompt)).toEqual([
      "What does the law say about …",
      "Review this contract",
      "Analyze this agreement",
      "Extract important clauses",
      "Identify contractual risks",
    ]);
  });

  it("marks contract review as requiring a file", () => {
    const review = getStarterPrompt("review");
    expect(review?.expectsFile).toBe(true);
    expect(review && starterConversationTitle(review)).toBe("Review contract");
  });

  it("returns undefined for an unknown starter", () => {
    expect(getStarterPrompt("unknown")).toBeUndefined();
  });
});
