// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Composer } from "@/components/chat/composer";

afterEach(cleanup);

describe("Composer cancellation behavior", () => {
  it("preserves text and files when a stopped send returns false", async () => {
    const onSend = vi.fn().mockResolvedValue(false);
    const user = userEvent.setup();
    const { container } = render(
      <Composer sending={false} onSend={onSend} />,
    );
    const question = screen.getByLabelText("Legal question");
    const file = new File(["context"], "context.txt", {
      type: "text/plain",
    });

    await user.type(question, "Preserve this draft");
    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      file,
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({
      message: "Preserve this draft",
      files: [file],
    });
    expect(question).toHaveValue("Preserve this draft");
    expect(screen.getByText("context.txt")).toBeInTheDocument();
  });
});
