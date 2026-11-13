import { defineConfig, devices } from "@playwright/test";

// Starts FastAPI and Next.js, then drives the app in a real browser.
// Locally, servers that are already running are reused. In CI both are started fresh,
// with a production build of the frontend.
// PW_CHANNEL picks an installed browser instead of Playwright's own Chromium, for
// example PW_CHANNEL=msedge on Windows.

const CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL || undefined },
    },
  ],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !CI,
      timeout: 60_000,
    },
    {
      command: CI ? "npm run build && npm run start" : "npm run dev",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !CI,
      timeout: 180_000,
    },
  ],
});
