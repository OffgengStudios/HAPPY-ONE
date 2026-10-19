import { expect, test } from "@playwright/test";

test("the foundation shell renders without errors or horizontal overflow", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveTitle("HAPPY Management Platform");
  await expect(
    page.getByRole("heading", {
      name: "HAPPY Management Platform",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  );
  expect(fits).toBe(true);
  const headerBackground = await page
    .locator("header")
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(headerBackground).toBe("rgb(255, 255, 255)");
  expect(errors).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("foundation.png"),
    fullPage: true,
  });
});
