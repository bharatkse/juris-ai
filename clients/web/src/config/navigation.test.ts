import { describe, expect, it } from "vitest";

import {
  allNavEntries,
  ICONS,
  profileMenuItems,
  SETTINGS_NAV,
  WORK_NAV,
} from "@/config/navigation";

describe("navigation config", () => {
  it("gives every work, settings, and profile item an icon and label", () => {
    for (const item of allNavEntries()) {
      expect(item.label.trim().length).toBeGreaterThan(0);
      expect(ICONS[item.icon]).toBeTruthy();
    }
    for (const item of profileMenuItems({ admin: true, permissions: true })) {
      expect(item.label.trim().length).toBeGreaterThan(0);
      expect(ICONS[item.icon]).toBeTruthy();
    }
    expect(WORK_NAV).toHaveLength(5);
    expect(SETTINGS_NAV.length).toBeGreaterThan(0);
  });
});
