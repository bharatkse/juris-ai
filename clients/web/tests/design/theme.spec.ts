import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const shots = fileURLToPath(new URL("./reference/theme", import.meta.url));

test("captures light and dark key screens", async ({ page }, testInfo) => {
  mkdirSync(shots, { recursive: true });
  const prefix = testInfo.project.name.includes("mobile") ? "mobile" : "desktop";

  async function shot(name: string) {
    await page.screenshot({
      path: path.join(shots, `${prefix}-${name}.png`),
      animations: "disabled",
    });
  }

  await page.addInitScript(() => {
    window.localStorage.setItem("juris-theme", "light");
  });
  await page.goto("/login");
  await expect(page.locator("html")).toHaveClass(/light/);
  await shot("login-light");

  await page.goto("/");
  await shot("landing-light");

  await page.evaluate(() => {
    document.documentElement.classList.remove("light");
    document.documentElement.classList.add("dark");
    window.localStorage.setItem("juris-theme", "dark");
  });
  await expect(page.locator("html")).toHaveClass(/dark/);
  await shot("landing-dark");

  await page.goto("/login");
  await shot("login-dark");
  await page.goto("/register");
  await shot("register-dark");
});
