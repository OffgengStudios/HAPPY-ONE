import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function expectAccessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
}

test("sign-in and authenticated Management surfaces have no automated WCAG A/AA violations", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expectAccessible(page);

  await page
    .getByLabel("Email", { exact: true })
    .fill("management@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Performance overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /KPI-PLC-002/ }).hover();
  await expectAccessible(page);
});

for (const role of [
  "admin",
  "demand",
  "supply",
  "matching",
  "merl",
  "marketing",
]) {
  test(`${role} default workspace has no automated WCAG A/AA violations`, async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByLabel("Email", { exact: true }).fill(`${role}@example.org`);
    await page.getByLabel("Password", { exact: true }).fill(password!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("navigation", { name: "Account navigation", exact: true }),
    ).toBeVisible();
    await expectAccessible(page);
  });
}
