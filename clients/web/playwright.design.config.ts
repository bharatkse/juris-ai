import { defineConfig } from "@playwright/test";

const baseURL =
  process.env.PLAYWRIGHT_DESIGN_BASE_URL ?? "http://127.0.0.1:3107";
const serverUrl = new URL(baseURL);
const port = serverUrl.port || "3107";

export default defineConfig({
  testDir: "./design/capture",
  testMatch: "reference.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  outputDir: "test-results/design-capture",
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
      name: "design-desktop",
      use: { viewport: { width: 1440, height: 900 } },
    },
    {
      name: "design-mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: {
    command: `npm run dev -- --hostname ${serverUrl.hostname} --port ${port}`,
    url: baseURL,
    reuseExistingServer: false,
  },
});
