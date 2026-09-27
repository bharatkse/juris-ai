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

  test("applies a stored light preference", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("juris-theme", "light");
    });
    await page.goto("/login");
    await expect(page.locator("html")).toHaveClass(/light/);
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("follows OS dark when theme is system", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript(() => {
      window.localStorage.setItem("juris-theme", "system");
    });
    await page.goto("/login");
    await expect(page.locator("html")).toHaveClass(/dark/);
  });

  test("theme toggle is keyboard accessible after mount", async ({ page }) => {
    await page.goto("/");
    const group = page.getByRole("radiogroup", { name: "Color theme" });
    await expect(group).toBeVisible();
    await group.getByRole("radio", { name: "Dark" }).press("Enter");
    await expect(page.locator("html")).toHaveClass(/dark/);
  });
});
