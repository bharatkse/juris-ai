// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfileMenu } from "@/components/layout/profile-menu";
import type { User } from "@/types/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/features/theme/provider", () => ({
  useTheme: () => ({
    theme: "light",
    resolvedTheme: "light",
    setTheme: vi.fn(),
  }),
}));

const user: User = {
  id: "user_1",
  email: "researcher@example.com",
  first_name: "Legal",
  last_name: "Researcher",
  gender: null,
  phone_number: null,
  date_of_birth: null,
  created_at: "2026-09-15T10:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

function renderMenu(capabilities = { admin: false, permissions: false }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProfileMenu user={user} capabilities={capabilities} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("ProfileMenu", () => {
  it("opens upward and hides role-gated items", async () => {
    const events = userEvent.setup();
    renderMenu();
    await events.click(screen.getByRole("button", { name: /legal researcher/iu }));
    expect(screen.getByRole("menu", { name: "Account" })).toBeVisible();
    expect(screen.getByRole("menuitem", { name: "Settings" })).toBeVisible();
    expect(screen.queryByRole("menuitem", { name: "Admin" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: "Permissions" }),
    ).not.toBeInTheDocument();
  });

  it("supports arrow keys and Escape", async () => {
    const events = userEvent.setup();
    renderMenu({ admin: true, permissions: true });
    const trigger = screen.getByRole("button", { name: /legal researcher/iu });
    await events.click(trigger);
    await events.keyboard("{ArrowDown}");
    await events.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
