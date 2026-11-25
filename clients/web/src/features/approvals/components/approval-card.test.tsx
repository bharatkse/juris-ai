// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApprovalCard } from "@/features/approvals/components/approval-card";

afterEach(cleanup);

describe("ApprovalCard", () => {
  it("shows payload JSON and approve, reject, and edit", async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined);
    render(
      <ApprovalCard
        approval={{
          approval_id: "approval_1",
          status: "waiting",
          expires_at: "2099-01-01T00:00:00Z",
          payload: { tool: "email_send", to: "a@b.c" },
        }}
        onDecision={onDecision}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Approval required" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/email_send/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();

    await userEvent
      .setup()
      .type(screen.getByLabelText("Decision reason (optional)"), "Reviewed");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Approve" }));

    expect(onDecision).toHaveBeenCalledWith("approve", { reason: "Reviewed" });
  });

  it("renders a terminal status with retry resume", () => {
    render(
      <ApprovalCard
        approval={{ approval_id: "approval_2", status: "rejected" }}
        onDecision={vi.fn()}
        onResume={vi.fn()}
      />,
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByRole("button", { name: "Retry resume" })).toBeInTheDocument();
  });
});
