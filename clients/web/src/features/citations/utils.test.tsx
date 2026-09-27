// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CitationChip } from "@/components/citations/citation-chip";
import {
  safeExternalUri,
  sourceForCitation,
} from "@/features/citations/utils";

afterEach(cleanup);

describe("citation trust helpers", () => {
  it("allows only HTTP source links", () => {
    expect(safeExternalUri("https://example.com/case")).toBe(
      "https://example.com/case",
    );
    expect(safeExternalUri("javascript:alert(1)")).toBeNull();
    expect(safeExternalUri("not a url")).toBeNull();
  });

  it("matches a citation to a real source without fabricating one", () => {
    const source = { title: "Maneka Gandhi", uri: "https://example.com" };
    expect(
      sourceForCitation(
        { title: "Maneka Gandhi", source: "Supreme Court" },
        [source],
      ),
    ).toBe(source);
    expect(
      sourceForCitation(
        { title: "Unknown", source: "Unknown reporter" },
        [source],
      ),
    ).toBeUndefined();
  });

  it("exposes an accessible, keyboard-clickable citation chip", async () => {
    const onClick = vi.fn();
    render(
      <CitationChip index={0} title="Constitution of India" onClick={onClick} />,
    );

    const chip = screen.getByRole("button", {
      name: "Open citation 1: Constitution of India",
    });
    await userEvent.setup().click(chip);
    expect(onClick).toHaveBeenCalledOnce();
    expect(chip).toHaveAttribute("aria-pressed", "false");
  });
});
