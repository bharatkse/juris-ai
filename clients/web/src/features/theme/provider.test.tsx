// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { THEME_STORAGE_KEY } from "@/config/theme";
import { ThemeProvider, useTheme } from "@/features/theme/provider";
import { ThemeToggle } from "@/features/theme/theme-toggle";

function Probe() {
  const { theme, resolvedTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
    </div>
  );
}

function mockMatchMedia(prefersDark: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("dark") ? prefersDark : !prefersDark,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.className = "";
    mockMatchMedia(false);
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("defaults to system and resolves to light when the OS is light", async () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent("system");
    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
  });

  it("resolves system to dark when prefers-color-scheme is dark", async () => {
    mockMatchMedia(true);
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("resolved")).toHaveTextContent("dark");
  });

  it("restores a stored preference", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent("dark");
  });

  it("falls back to system when storage is invalid", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "neon");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent("system");
  });

  it("lets ThemeToggle persist a choice", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
        <Probe />
      </ThemeProvider>,
    );
    await screen.findByRole("radiogroup", { name: "Color theme" });
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(await screen.findByTestId("theme")).toHaveTextContent("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("applies the dark class on html", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    await screen.findByTestId("theme");
    await act(async () => {
      await Promise.resolve();
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
