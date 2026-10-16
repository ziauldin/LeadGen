import { defineConfig, devices } from "@playwright/test";

// End-to-end smoke test against a real API (fresh SQLite DB, background jobs run inline)
// and a production build of the web app. Run with `npm run e2e`.
const python = process.env.E2E_PYTHON ?? "python";
const apiPort = 8010;
const webPort = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} scripts/e2e_api.py`,
      cwd: "../../services/api",
      url: `http://localhost:${apiPort}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { E2E_API_PORT: String(apiPort), E2E_WEB_URL: `http://localhost:${webPort}` },
    },
    {
      command: `npm run build && npx next start -p ${webPort}`,
      url: `http://localhost:${webPort}/healthz`,
      timeout: 300_000,
      reuseExistingServer: false,
      env: { API_INTERNAL_URL: `http://localhost:${apiPort}` },
    },
  ],
});
