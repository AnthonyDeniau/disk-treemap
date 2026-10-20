import { test, expect } from "@playwright/test";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  readFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";

let temporary: string;
let report: string;
test.beforeAll(() => {
  temporary = mkdtempSync(join(tmpdir(), "disk-treemap-e2e-"));
  const input = join(temporary, "synthetic-input");
  mkdirSync(join(input, "nested"), { recursive: true });
  writeFileSync(join(input, "example.bin"), Buffer.alloc(8192, 1));
  writeFileSync(join(input, "empty.txt"), "");
  writeFileSync(join(input, "nested", "small.txt"), "synthetic");
  report = join(temporary, "report with spaces.html");
  execFileSync(
    process.env.PYTHON || "python3",
    [
      "-m",
      "disk_treemap",
      input,
      "-o",
      report,
      "--chunk-size",
      "2",
      "--size",
      "logical",
      "--label",
      "</script><script>window.unwanted=true</script>",
    ],
    {
      env: { ...process.env, PYTHONPATH: resolve("src") },
      stdio: "pipe",
    },
  );
});
test.afterAll(() => rmSync(temporary, { recursive: true, force: true }));

test("offline chunks, click details, keyboard contents and zero-byte entries", async ({
  page,
}) => {
  const errors: string[] = [];
  const remote: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (/^https?:/.test(request.url())) remote.push(request.url());
  });
  await page.goto(pathToFileURL(report).href);
  await expect(page.getByRole("status")).toHaveCount(0);
  const canvas = page.locator("canvas");
  await canvas.click({ position: { x: 20, y: 20 } });
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator("#file-name")).toHaveText("example.bin");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await canvas.focus();
  await page.keyboard.press("Enter");
  await page.getByText(/^Folder contents/).click();
  await page.getByRole("button", { name: /empty.txt/ }).click();
  await expect(page.locator("#file-name")).toHaveText("empty.txt");
  await expect(page.locator(".file-bytes")).toHaveText("0 B");
  expect(
    await page.evaluate(
      () => (window as unknown as { unwanted?: boolean }).unwanted,
    ),
  ).toBeUndefined();
  expect(errors).toEqual([]);
  expect(remote).toEqual([]);
});

test("folder zoom, parent navigation and a small viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 750 });
  await page.goto(pathToFileURL(report).href);
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.locator("canvas").focus();
  await page.keyboard.press("Enter");
  await page.getByText(/^Folder contents/).click();
  await page.getByRole("button", { name: /nested/ }).click();
  await page.getByRole("button", { name: "Explore this folder →" }).click();
  await expect(
    page.getByRole("button", { name: "Parent folder", exact: true }),
  ).toBeVisible();
  await page.locator("canvas").click({ position: { x: 100, y: 100 } });
  await expect(page.locator("#file-name")).toHaveText("small.txt");
  const box = await page.getByRole("dialog").boundingBox();
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Scan root", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Parent folder", exact: true }),
  ).toHaveCount(0);
});

test("missing data is reported with a useful recovery message", async ({
  page,
}) => {
  const html = readFileSync(report, "utf8").replace(
    /disk-treemap-data-[a-f0-9]{12}/g,
    "disk-treemap-data-000000000000",
  );
  const broken = join(temporary, "missing-data.html");
  writeFileSync(broken, html);
  await page.goto(pathToFileURL(broken).href);
  await expect(page.getByRole("status")).toContainText(
    "Keep the HTML and its data folder together",
  );
});

test("synthetic demo loads without scan metadata", async ({ page }) => {
  await page.goto(
    pathToFileURL(resolve("src/disk_treemap/assets/viewer.html")).href,
  );
  await expect(page.locator("canvas")).toBeVisible();
  await page.locator("canvas").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#file-name")).toHaveText(
    "Example disk (synthetic data)",
  );
});
