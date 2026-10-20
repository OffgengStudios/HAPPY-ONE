import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("marketing@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Requests", exact: true }),
  ).toBeVisible();
}

async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

test("Marketing staff receives a request and moves a campaign into production", async ({
  page,
}, info) => {
  await login(page);
  await page.getByRole("button", { name: "New request", exact: true }).click();
  let dialog = page.getByRole("dialog", {
    name: "Create marketing request",
    exact: true,
  });
  await dialog.getByLabel("Request type").selectOption("TRAINING_PROMOTION");
  await dialog
    .getByLabel("Linked training")
    .selectOption({ label: `Browser Training ${info.project.name}` });
  await dialog
    .locator("textarea")
    .fill(`Recruitment promotion ${info.project.name}`);
  await dialog.getByLabel("Priority").selectOption("HIGH");
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/marketing/requests") &&
      response.request().method() === "POST",
  );
  await save(page, "Create marketing request");
  const response = await created;
  expect(response.status()).toBe(201);
  const request = await response.json();
  await expect(
    page
      .getByRole("button", { name: new RegExp(request.request_code) })
      .getByText("Training promotion", { exact: true }),
  ).toBeVisible();

  await navigate(page, "Campaigns");
  await page.getByRole("button", { name: "New campaign", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Create campaign", exact: true });
  await dialog
    .locator('input[type="text"]')
    .fill(`Browser Campaign ${info.project.name}`);
  await dialog.getByLabel("Campaign type").selectOption("TRAINING");
  await dialog
    .getByLabel("Linked training")
    .selectOption({ label: `Browser Training ${info.project.name}` });
  await dialog.locator("textarea").nth(0).fill("Jobseekers in Accra");
  await dialog.locator("textarea").nth(1).fill('["APPROVED_TEST_CHANNEL"]');
  await save(page, "Create campaign");
  const campaign = page.getByRole("button", {
    name: new RegExp(`Browser Campaign ${info.project.name}`),
  });
  await expect(campaign).toBeVisible();
  await campaign.click();
  await page
    .getByRole("button", { name: "Move campaign", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Move campaign", exact: true });
  await dialog.locator("select").selectOption("IN_PRODUCTION");
  await dialog.locator("textarea").fill("Creative production started.");
  await save(page, "Move campaign");
  await expect(page.getByText("In production", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Add asset", exact: true }).click();
  dialog = page.getByRole("dialog", {
    name: "Add campaign asset",
    exact: true,
  });
  await dialog.locator("select").selectOption("SOCIAL_COPY");
  await dialog
    .locator('input[type="text"]')
    .fill(`Browser Copy ${info.project.name}`);
  await dialog.locator("textarea").fill("Approved synthetic recruitment copy.");
  await save(page, "Add campaign asset");
  const asset = page.getByRole("button", {
    name: new RegExp(`Browser Copy ${info.project.name}`),
  });
  await asset.click();
  dialog = page.getByRole("dialog", {
    name: "Review campaign asset",
    exact: true,
  });
  await dialog.locator("select").selectOption("APPROVED");
  await dialog.locator("textarea").fill("Content review completed.");
  await save(page, "Review campaign asset");
  await expect(asset.getByText("Approved", { exact: true })).toBeVisible();

  await navigate(page, "Dashboard");
  await expect(
    page.getByRole("heading", { name: "Marketing Dashboard", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Open requests", { exact: true })).toBeVisible();
});
