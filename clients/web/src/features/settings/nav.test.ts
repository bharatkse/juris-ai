import { describe, expect, it } from "vitest";

import { isSettingsPathActive, visibleSettingsNav } from "@/features/settings/nav";
import { profileMenuItems } from "@/features/settings/profile-menu-items";

describe("settings navigation", () => {
  it("hides permissions without the capability", () => {
    const items = visibleSettingsNav({ admin: false, permissions: false });
    expect(items.map((item) => item.id)).not.toContain("permissions");
  });

  it("marks memory nested routes active", () => {
    expect(isSettingsPathActive("/settings/memory/abc", "/settings/memory")).toBe(
      true,
    );
    expect(isSettingsPathActive("/settings/profile", "/settings/memory")).toBe(
      false,
    );
  });
});

describe("profile menu items", () => {
  it("hides admin and permissions by default", () => {
    const ids = profileMenuItems({ admin: false, permissions: false }).map(
      (item) => item.id,
    );
    expect(ids).not.toContain("admin");
    expect(ids).not.toContain("permissions");
    expect(ids).toContain("settings");
    expect(ids).toContain("memory");
  });

  it("shows role-gated items when allowed", () => {
    const ids = profileMenuItems({ admin: true, permissions: true }).map(
      (item) => item.id,
    );
    expect(ids).toContain("admin");
    expect(ids).toContain("permissions");
  });
});
