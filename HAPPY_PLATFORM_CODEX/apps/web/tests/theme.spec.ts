import { expect, test } from "@playwright/test";
import { navigate } from "./navigation";

test("HAPPY uses the prototype's recruitment-blue accents and typography", async ({
  page,
}, info) => {
  await page.goto("/");
  const command = page.getByRole("button", { name: "Sign in", exact: true });
  await expect(command).toHaveCSS("background-color", "rgb(0, 74, 185)");
  await expect(command).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(
    page.getByRole("heading", { name: "HAPPY Management Platform" }),
  ).toHaveCSS("color", "rgb(0, 74, 185)");
  const font = await page
    .locator("body")
    .evaluate((element) => getComputedStyle(element).fontFamily);
  expect(font).toContain("Arial");
  await page.screenshot({
    path: info.outputPath("blue-sign-in.png"),
    fullPage: true,
  });
});

test("primary commands follow shared theme tokens, including hover", async ({
  page,
}, info) => {
  await page.goto("/");
  const command = page.getByRole("button", { name: "Sign in", exact: true });
  await expect(command).toBeVisible();
  await page.screenshot({
    path: info.outputPath("blue-token-sign-in.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    const root = document.documentElement;
    root.style.setProperty("--primary", "0 100% 40%");
    root.style.setProperty("--primary-hover", "0 100% 25%");
    root.style.setProperty("--primary-foreground", "60 100% 90%");
  });
  await expect(command).toHaveCSS("background-color", "rgb(204, 0, 0)");
  await expect(command).toHaveCSS("border-top-color", "rgb(204, 0, 0)");
  await expect(command).toHaveCSS("color", "rgb(255, 255, 204)");
  await command.hover();
  await expect(command).toHaveCSS("background-color", "rgb(128, 0, 0)");
});

test("selected account navigation follows shared theme tokens", async ({
  page,
  isMobile,
}, info) => {
  const password = process.env.HAPPY_E2E_PASSWORD;
  test.skip(!password, "Run pnpm verify with the isolated browser API.");
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const active = page
    .getByRole("navigation", { name: "Account navigation" })
    .locator('[aria-current="page"]');
  await expect(active).toBeVisible();
  if (!isMobile) {
    const sidebar = page.locator(".account-sidebar");
    await expect(sidebar).toHaveCSS("background-color", "rgb(16, 26, 56)");
    await expect(sidebar).toHaveCSS("position", "fixed");
    await expect(
      sidebar.getByRole("navigation", { name: "Account navigation" }),
    ).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(
      sidebar.getByRole("combobox", { name: "Workspace", exact: true }),
    ).toHaveCSS("color", "rgb(31, 41, 55)");
    const box = (await sidebar.boundingBox())!;
    expect(box.x).toBe(0);
    expect(box.y).toBe(0);
    expect(box.width).toBe(260);
    expect(box.height).toBe(page.viewportSize()!.height);
    const search = (await page
      .getByRole("button", { name: "Global search", exact: true })
      .boundingBox())!;
    expect(search.x).toBeGreaterThanOrEqual(260);
    expect(search.width).toBeGreaterThan(200);
    await expect(
      page.getByRole("button", { name: "Account menu", exact: true }),
    ).toHaveCSS("border-radius", "9999px");
  }
  await page.screenshot({
    path: info.outputPath("blue-navigation.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    const root = document.documentElement;
    root.style.setProperty("--primary", "0 100% 40%");
    root.style.setProperty("--primary-subtle", "0 100% 95%");
    root.style.setProperty("--sidebar-active", "0 100% 95%");
    root.style.setProperty("--sidebar-foreground", "0 100% 40%");
    root.style.setProperty("--primary-foreground", "0 100% 40%");
  });
  await expect(active).toHaveCSS("background-color", "rgb(255, 230, 230)");
  await expect(active).toHaveCSS("color", "rgb(204, 0, 0)");
});

for (const reducedMotion of ["no-preference", "reduce"] as const) {
  test(`surface motion respects ${reducedMotion} without delaying focus or actions`, async ({
    page,
  }, info) => {
    const password = process.env.HAPPY_E2E_PASSWORD;
    test.skip(!password, "Run pnpm verify with the isolated browser API.");
    await page.emulateMedia({ reducedMotion });
    await page.goto("/");
    await expect(page.locator(".sign-in-surface")).toHaveCSS(
      "animation-name",
      reducedMotion === "reduce" ? "none" : "surface-enter",
    );
    await page.getByLabel("Email", { exact: true }).fill("admin@example.org");
    await page.getByLabel("Password", { exact: true }).fill(password!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    const account = page.getByRole("button", {
      name: "Account menu",
      exact: true,
    });
    await account.click();
    const menu = page.getByRole("menu", { name: "Account", exact: true });
    await expect(menu).toHaveCSS(
      "animation-name",
      reducedMotion === "reduce" ? "none" : "surface-enter",
    );
    await expect(
      menu.getByRole("menuitem", { name: "Account security", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(account).toBeFocused();
    await navigate(page, "Employers");
    await page
      .getByRole("button", { name: "New employer", exact: true })
      .click();
    const dialog = page.getByRole("dialog", {
      name: "New employer",
      exact: true,
    });
    const mobile = page.viewportSize()!.width < 768;
    await expect(dialog).toHaveCSS(
      "animation-name",
      reducedMotion === "reduce"
        ? "none"
        : mobile
          ? "sheet-enter"
          : "drawer-enter",
    );
    await dialog
      .getByLabel("Employer name", { exact: true })
      .fill("Unsubmitted motion review");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(dialog).toHaveCSS("animation-name", "none");
    await expect(
      dialog.getByLabel("Employer name", { exact: true }),
    ).toHaveValue("Unsubmitted motion review");
    expect(
      await page
        .getByRole("region", { name: "Workspace content", exact: true })
        .evaluate(
          (element) =>
            element
              .getAnimations()
              .filter((animation) => animation.playState === "running").length,
        ),
    ).toBe(0);
    await page.screenshot({
      path: info.outputPath(`blue-${reducedMotion}-drawer.png`),
    });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "New employer", exact: true }),
    ).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}
