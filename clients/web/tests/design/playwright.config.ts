import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const packageRoot = fileURLToPath(new URL("../..", import.meta.url));
const baseURL =
  process.env.PLAYWRIGHT_DESIGN_BASE_URL ?? "http://127.0.0.1:3107";
const serverUrl = new URL(baseURL);
const port = serverUrl.port || "3107";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: "line",
  outputDir: "../../test-results/design-capture",
  use: {
    baseURL,
    channel: "chrome",
    deviceScaleFactor: 1,
    colorScheme: "light",
    locale: "en-US",
    timezoneId: "UTC",
    reducedMotion: "reduce",
    trace: "off",
  },
  projects: [
    {
      name: "design-360",
      use: {
        viewport: { width: 360, height: 800 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "design-768",
      use: { viewport: { width: 768, height: 1024 } },
    },
    {
      name: "design-1440",
      use: { viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: `npm run dev -- --hostname ${serverUrl.hostname} --port ${port}`,
    cwd: packageRoot,
    url: baseURL,
    reuseExistingServer: false,
  },
});
