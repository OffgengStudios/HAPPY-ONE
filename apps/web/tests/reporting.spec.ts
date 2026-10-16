import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill("management@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Performance overview", exact: true }),
  ).toBeVisible();
}

test("Management can inspect KPI evidence and export bounded or prepared reports", async ({
  page,
}) => {
  await login(page);
  const confirmed = page.getByRole("button", {
    name: /KPI-PLC-001.*Confirmed placements/s,
  });
  const confirmedCount = Number(
    await confirmed.locator("strong").textContent(),
  );
  expect(confirmedCount).toBeGreaterThanOrEqual(2);
  await confirmed.click();
  await expect(
    page.getByRole("heading", { name: "Confirmed placements", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/PLC-BROWSER-MERL-/).first()).toBeVisible();

  await navigate(page, "Reports & Targets");
  await expect(
    page.getByRole("heading", { name: "Exportable reports", exact: true }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download bounded Confirmed placements" })
    .click();
  const report = await downloadPromise;
  expect(report.suggestedFilename()).toBe("kpi-plc-001.csv");

  await page
    .getByRole("button", { name: "Prepare full Confirmed placements" })
    .click();
  const prepared = page
    .getByRole("heading", { name: "Prepared exports", exact: true })
    .locator("..");
  await expect(prepared.getByText(/succeeded/i)).toBeVisible();
  await expect(
    prepared.getByRole("button", {
      name: "Download prepared KPI-PLC-001",
      exact: true,
    }),
  ).toBeVisible();
});
