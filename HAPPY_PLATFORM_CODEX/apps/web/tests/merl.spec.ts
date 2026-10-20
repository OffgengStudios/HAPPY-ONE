import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("merl@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Follow-ups", exact: true }),
  ).toBeVisible();
}

async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

async function selectPlacement(page: Page, title: string, projection: string) {
  const field = page
    .getByRole("dialog", { name: title, exact: true })
    .locator("select")
    .first();
  const value = await field.evaluate((element, expected) => {
    const select = element as HTMLSelectElement;
    return Array.from(select.options).find((option) =>
      option.text.includes(`Esi MERL Fixture ${expected}`),
    )?.value;
  }, projection);
  expect(value).toBeTruthy();
  await field.selectOption(value!);
}

test("MERL staff schedules a follow-up, records an outcome and sees dashboard evidence", async ({
  page,
}, info) => {
  await login(page);
  await page.getByRole("button", { name: "Schedule", exact: true }).click();
  let dialog = page.getByRole("dialog", {
    name: "Schedule follow-up",
    exact: true,
  });
  await selectPlacement(page, "Schedule follow-up", info.project.name);
  await dialog.locator("select").nth(1).selectOption("EMPLOYMENT_VERIFICATION");
  await dialog.locator('input[type="date"]').fill("2026-10-12");
  await save(page, "Schedule follow-up");

  await page
    .getByRole("button", {
      name: new RegExp(`Esi MERL Fixture ${info.project.name}`),
    })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Complete follow-up",
    exact: true,
  });
  await dialog.locator("select").selectOption("REACHED");
  await dialog
    .locator("textarea")
    .fill("Participant reached and employment verified.");
  await save(page, "Complete follow-up");

  await navigate(page, "Outcomes");
  await page
    .getByRole("button", { name: "Record outcome", exact: true })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Record verified outcome",
    exact: true,
  });
  await selectPlacement(page, "Record verified outcome", info.project.name);
  await dialog.locator("select").nth(1).selectOption({ index: 1 });
  await dialog.locator('input[type="date"]').fill("2026-10-12");
  await dialog.locator('input[type="checkbox"]').nth(0).check();
  await dialog
    .locator('input[type="text"]')
    .nth(1)
    .fill("Read-only Browser Vacancy");
  await dialog.locator('input[type="checkbox"]').nth(1).check();
  await save(page, "Record verified outcome");
  const outcome = page.locator(".data-row").filter({
    has: page.getByText(`Esi MERL Fixture ${info.project.name}`, {
      exact: true,
    }),
  });
  await expect(
    outcome.getByText("Impact story", { exact: true }),
  ).toBeVisible();

  await navigate(page, "Dashboard");
  await expect(
    page.getByRole("heading", { name: "Outcome Dashboard", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Impact stories", { exact: true })).toBeVisible();
});
