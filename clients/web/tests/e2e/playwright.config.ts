import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const packageRoot = fileURLToPath(new URL("../..", import.meta.url));
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3110";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  outputDir: "../../test-results/e2e",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npx next dev --hostname 0.0.0.0 --port 3110",
    cwd: packageRoot,
    url: `${baseURL}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
