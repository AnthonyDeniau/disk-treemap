import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "web/e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  use: { viewport: { width: 1280, height: 800 }, trace: "retain-on-failure" },
});
