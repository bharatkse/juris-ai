// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { MessageList } from "@/features/chat/components/message-list";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(cleanup);

describe("MessageList streaming state", () => {
  it("marks progressive content as a draft without a Stop control", () => {
    render(
      <MessageList
        events={[]}
        pending={{ content: "Question", files: [] }}
        streamProgress={{
          status: "working",
          phase: "answering",
          draftContent: "Uncommitted draft content",
        }}
        answerDetails={{}}
        approvalStates={{}}
        userFiles={{}}
        onOpenCitations={vi.fn()}
        onApprovalDecision={vi.fn()}
      />,
    );

    expect(screen.getByText("Answering")).toBeInTheDocument();
    expect(screen.getByText("Drafting · not final")).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: "Juris AI draft response" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Uncommitted draft content")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
  });
});
