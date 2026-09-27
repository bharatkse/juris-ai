// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { MessageList } from "@/components/chat/message-list";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(cleanup);

describe("MessageList streaming state", () => {
  it("marks progressive content as a draft and exposes Stop", async () => {
    const onStop = vi.fn();
    render(
      <MessageList
        events={[]}
        pending={{ content: "Question", files: [] }}
        streamProgress={{
          status: "working",
          phase: "answering",
          draftContent: "Uncommitted draft content",
        }}
        streamActive
        answerDetails={{}}
        approvalStates={{}}
        userFiles={{}}
        onStop={onStop}
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

    await userEvent.setup().click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalledOnce();
  });
});
