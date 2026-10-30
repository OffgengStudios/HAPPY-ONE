import { expect, type Page } from "@playwright/test";

export async function navigate(page: Page, name: string) {
  await expect(
    page.getByRole("navigation", { name: "Account navigation", exact: true }),
  ).toBeVisible();
  const item = page
    .getByRole("navigation", { name: "Account navigation", exact: true })
    .getByRole("button", { name, exact: true });
  if (await item.isVisible()) {
    await item.click();
    return;
  }
  await page.getByRole("button", { name: "More", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "More", exact: true });
  await menu.getByRole("button", { name, exact: true }).click();
  await expect(menu).toHaveCount(0);
}

export async function signOut(page: Page) {
  await page.getByRole("button", { name: "Account menu", exact: true }).click();
  await page
    .getByRole("menu", { name: "Account", exact: true })
    .getByRole("menuitem", { name: "Sign out", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
}
