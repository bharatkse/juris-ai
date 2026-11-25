// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_THEME, THEME_STORAGE_KEY } from "@/config/theme";
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

  it("defaults to light and does not follow the OS", async () => {
    mockMatchMedia(true);
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent(DEFAULT_THEME);
    expect(screen.getByTestId("resolved")).toHaveTextContent(DEFAULT_THEME);
    expect(document.documentElement.classList.contains("dark")).toBe(
      DEFAULT_THEME === "dark",
    );
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

  it("migrates a stored system value to the env default", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "system");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent(DEFAULT_THEME);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe(DEFAULT_THEME);
  });

  it("falls back to the env default when storage is invalid", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "neon");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(await screen.findByTestId("theme")).toHaveTextContent(DEFAULT_THEME);
  });

  it("lets ThemeToggle persist a choice", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
        <Probe />
      </ThemeProvider>,
    );
    const next = DEFAULT_THEME === "dark" ? "light" : "dark";
    const toggle = await screen.findByRole("button", {
      name: new RegExp(`Switch to ${next} theme`, "i"),
    });
    await user.click(toggle);
    expect(await screen.findByTestId("theme")).toHaveTextContent(next);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe(next);
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
