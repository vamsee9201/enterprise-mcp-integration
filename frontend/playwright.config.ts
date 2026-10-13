import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  use: {
    baseURL: "http://localhost:3020",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: ".venv/bin/python scripts/e2e_backend.py",
      cwd: "../",
      url: "http://127.0.0.1:8020/health",
      timeout: 60000,
      reuseExistingServer: false,
    },
    {
      command:
        process.env.PLAYWRIGHT_PRODUCTION === "1"
          ? "node ../scripts/e2e_frontend.mjs"
          : "npm run dev -- --port 3020",
      env: {
        API_INTERNAL_URL: "http://127.0.0.1:8020",
        NEXT_TELEMETRY_DISABLED: "1",
      },
      url: "http://localhost:3020",
      timeout: 120000,
      reuseExistingServer: false,
    },
  ],
});
