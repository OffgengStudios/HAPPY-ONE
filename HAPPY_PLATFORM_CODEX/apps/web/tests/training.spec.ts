import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("supply@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Account navigation", exact: true }),
  ).toBeVisible();
  await navigate(page, "Training");
}

async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

test("Supply staff creates training and records participant completion", async ({
  page,
}, info) => {
  test.setTimeout(90000);
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Training", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New training", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "New training", exact: true });
  const title = `Browser employability ${info.project.name}`;
  await dialog.getByLabel("Training title").fill(title);
  await dialog.getByLabel("Training type").fill("EMPLOYABILITY");
  await dialog.getByLabel("Trainer type").selectOption("INTERNAL");
  await dialog.getByLabel("Delivery mode").selectOption("IN_PERSON");
  await dialog.getByLabel("Start date").fill("2026-10-14");
  await dialog.getByLabel("Location").fill("Accra training centre");
  await dialog
    .getByLabel("Planned modules (one per line)")
    .fill("CV\nINTERVIEW");
  await dialog.getByLabel("Status").selectOption("IN_PROGRESS");
  await save(page, "New training");

  dialog = page.getByRole("dialog", { name: "Training details", exact: true });
  await expect(
    dialog.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Add participant", exact: true })
    .click();
  const add = page.getByRole("dialog", {
    name: "Add participant",
    exact: true,
  });
  await add.getByLabel("Participant").selectOption({ index: 1 });
  await add.getByRole("button", { name: "Add", exact: true }).click();
  await expect(add).toHaveCount(0);

  await dialog.getByRole("button", { name: /present · not started/i }).click();
  const attendance = page.getByRole("dialog", {
    name: "Update attendance",
    exact: true,
  });
  await attendance.getByLabel("Attendance").selectOption("PRESENT");
  await attendance.getByLabel("Completion").selectOption("COMPLETED");
  await attendance
    .getByLabel("Notes")
    .fill("Completed browser training fixture.");
  await save(page, "Update attendance");
  await expect(
    dialog.getByRole("button", { name: /present · completed/i }),
  ).toBeVisible();
});
