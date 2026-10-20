// The packaged template has placeholders, so it renders only the synthetic demo.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  await page.goto(
    pathToFileURL(resolve("src/disk_treemap/assets/viewer.html")).href,
  );
  await page.locator("canvas").waitFor();
  await page.locator("canvas").focus();
  await page.keyboard.press("Enter");
  const heading = await page.locator("#file-name").textContent();
  if (heading !== "Example disk (synthetic data)")
    throw new Error("Refusing to capture non-synthetic data");
  await page.keyboard.press("Escape");
  await page.locator("canvas").blur();
  mkdirSync("docs", { recursive: true });
  await page.screenshot({ path: "docs/demo.png" });
} finally {
  await browser.close();
}
