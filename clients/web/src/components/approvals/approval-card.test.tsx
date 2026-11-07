// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApprovalCard } from "@/components/approvals/approval-card";

afterEach(cleanup);

describe("ApprovalCard", () => {
  it("offers only approve and reject for a waiting approval", async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined);
    render(
      <ApprovalCard
        approval={{
          approval_id: "approval_1",
          status: "waiting",
          expires_at: "2099-01-01T00:00:00Z",
        }}
        onDecision={onDecision}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Approval required" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).toBeNull();

    await userEvent
      .setup()
      .type(screen.getByLabelText("Decision reason (optional)"), "Reviewed");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Approve" }));

    expect(onDecision).toHaveBeenCalledWith("approve", "Reviewed");
  });

  it("renders a terminal status without decision controls", () => {
    render(
      <ApprovalCard
        approval={{ approval_id: "approval_2", status: "rejected" }}
        onDecision={vi.fn()}
      />,
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});
