import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("matching@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My Work", exact: true }),
  ).toBeVisible();
}

async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

test("Matching staff records start, verifies first income and preserves a placement after exit", async ({
  page,
}, info) => {
  test.setTimeout(90000);
  await login(page);
  await navigate(page, "Placements");
  await page
    .getByRole("button", { name: "New placement", exact: true })
    .click();
  let dialog = page.getByRole("dialog", {
    name: "Create placement",
    exact: true,
  });
  await dialog
    .getByRole("combobox", { name: "Selected candidate", exact: true })
    .selectOption({
      label: `Kojo Placement Fixture ${info.project.name} | Read-only Browser Vacancy`,
    });
  await dialog
    .getByLabel("Expected start date", { exact: true })
    .fill("2026-10-10");
  await dialog.getByLabel("PLACEMENT INCOME", { exact: true }).fill("2400");
  await dialog.getByLabel("Monthly payday", { exact: true }).fill("25");
  await dialog.getByLabel("Monthly payroll cutoff", { exact: true }).fill("15");
  await save(page, "Create placement");

  await page
    .getByRole("button", { name: "Confirm start", exact: true })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Confirm actual start",
    exact: true,
  });
  await dialog
    .getByLabel("Actual start date", { exact: true })
    .fill("2026-10-10");
  await dialog
    .getByLabel("Verification note", { exact: true })
    .fill("Employer and participant confirmed start");
  await save(page, "Confirm actual start");
  await expect(page.getByText("2026-10-25", { exact: true })).toBeVisible();

  await page
    .getByRole("button", { name: "Confirm income", exact: true })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Confirm first income",
    exact: true,
  });
  await dialog
    .getByLabel("Income received date", { exact: true })
    .fill("2026-10-25");
  await dialog.getByLabel("Amount received", { exact: true }).fill("2400");
  await dialog
    .getByLabel("Verification evidence", { exact: true })
    .fill("Participant and payroll evidence verified");
  await save(page, "Confirm first income");
  await expect(
    page.getByText("Confirmed", { exact: true }).first(),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Employment ended", exact: true })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Record employment end",
    exact: true,
  });
  await dialog
    .getByLabel("Employment end date", { exact: true })
    .fill("2026-12-15");
  await dialog.getByLabel("Reason", { exact: true }).fill("Contract completed");
  await save(page, "Record employment end");
  await expect(page.getByText("Ended", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("No", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
