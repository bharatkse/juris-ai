import { expect, test } from "@playwright/test";

test.describe("theming", () => {
  test("applies a stored dark preference without a light first paint", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("juris-theme", "dark");
    });
    await page.goto("/login", { waitUntil: "commit" });
    await expect(page.locator("html")).toHaveClass(/dark/);
    const scheme = await page.locator("html").evaluate((el) =>
      getComputedStyle(el).colorScheme,
    );
    expect(scheme).toContain("dark");
  });

  test("applies a stored light preference with a white canvas", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("juris-theme", "light");
    });
    await page.goto("/login");
    await expect(page.locator("html")).toHaveClass(/light/);
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    const background = await page.locator("body").evaluate((el) =>
      getComputedStyle(el).backgroundColor,
    );
    expect(background).toBe("rgb(255, 255, 255)");
  });

  test("migrates a stored system value to light", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("juris-theme", "system");
    });
    await page.goto("/login");
    await expect(page.locator("html")).toHaveClass(/light/);
    const stored = await page.evaluate(() =>
      window.localStorage.getItem("juris-theme"),
    );
    expect(stored).toBe("light");
  });

  test("theme toggle is keyboard accessible after mount", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: /Switch to dark theme/i });
    await expect(toggle).toBeVisible();
    await toggle.press("Enter");
    await expect(page.locator("html")).toHaveClass(/dark/);
  });
});
