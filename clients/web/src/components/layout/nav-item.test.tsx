// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NavItem, NAV_ICON_SLOT, NAV_LABEL_CLASS } from "@/components/layout/nav-item";
import { ICONS } from "@/config/navigation";

afterEach(cleanup);

describe("NavItem alignment", () => {
  it("uses a shared icon slot so labels share an x-offset", () => {
    const { container } = render(
      <div>
        <NavItem icon={ICONS.newChat} label="New chat" />
        <NavItem icon={ICONS.search} label="Search" href="/app" />
        <NavItem icon={ICONS.documents} label="Documents" href="/app/documents" />
      </div>,
    );
    const slots = container.querySelectorAll(".nav-icon-slot");
    const labels = container.querySelectorAll(".nav-item-label");
    expect(slots).toHaveLength(3);
    expect(labels).toHaveLength(3);
    expect(NAV_ICON_SLOT).toContain("size-5");
    expect(NAV_ICON_SLOT).toContain("shrink-0");
    expect(NAV_LABEL_CLASS).toContain("truncate");
    const firstSlot = slots[0] as HTMLElement;
    const secondSlot = slots[1] as HTMLElement;
    expect(firstSlot.className).toBe(secondSlot.className);
  });
});
