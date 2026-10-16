import { expect, type Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page, email = "admin@example.org") {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Account navigation", exact: true }),
  ).toBeVisible();
}

test("the account shell uses a sidebar on desktop and a compact bottom bar on mobile", async ({
  page,
  isMobile,
}, info) => {
  await login(page);
  const navigation = page.getByRole("navigation", {
    name: "Account navigation",
    exact: true,
  });
  const position = await navigation.evaluate(
    (element) => getComputedStyle(element).position,
  );
  expect(position).toBe(isMobile ? "fixed" : "static");
  const more = navigation.getByRole("button", { name: "More", exact: true });
  if (isMobile) {
    await expect(more).toBeVisible();
    await expect(navigation.getByRole("button")).toHaveCount(4);
    const navBox = (await navigation.boundingBox())!;
    expect(
      Math.abs(navBox.y + navBox.height - page.viewportSize()!.height),
    ).toBeLessThan(2);
    const headingBox = (await page
      .getByRole("heading", { name: "My Work", exact: true })
      .boundingBox())!;
    expect(headingBox.y).toBeLessThan(200);
    expect(headingBox.y + headingBox.height).toBeLessThan(navBox.y);
    await page.evaluate(() =>
      window.scrollTo(0, document.documentElement.scrollHeight),
    );
    const content = page.locator("main > div > section");
    const contentBox = (await content.boundingBox())!;
    expect(contentBox.y + contentBox.height).toBeLessThanOrEqual(navBox.y);
  } else {
    await expect(more).toHaveCount(0);
    await expect(
      navigation.getByRole("button", { name: "Accounts", exact: true }),
    ).toBeVisible();
    expect((await navigation.boundingBox())!.width).toBeLessThan(240);
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("account-shell.png"),
    fullPage: true,
  });
});

test("workspace navigation adapts without losing overflow access or keyboard dismissal", async ({
  page,
  isMobile,
}, info) => {
  await login(page);
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption("SUPPLY");
  await expect(
    page.getByRole("heading", { name: "My Work", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Account navigation", exact: true })
      .getByRole("button", { name: "Participants", exact: true }),
  ).toBeVisible();
  if (isMobile) {
    await page.setViewportSize({ width: 320, height: 700 });
    const more = page.getByRole("button", { name: "More", exact: true });
    await more.click();
    const menu = page.getByRole("dialog", { name: "More", exact: true });
    await expect(menu).toBeVisible();
    await expect(
      menu.getByRole("button", { name: "Accounts", exact: true }),
    ).toBeVisible();
    await expect(
      menu.getByRole("button", { name: "Employers", exact: true }),
    ).toBeVisible();
    await expect
      .poll(async () => {
        const box = (await menu.boundingBox())!;
        return Math.abs(box.y + box.height - 700);
      })
      .toBeLessThan(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("more-sheet-narrow.png"),
      fullPage: true,
    });
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(more).toBeFocused();
  }
  await navigate(page, "Accounts");
  await expect(
    page.getByRole("heading", { name: "Accounts", exact: true }),
  ).toBeVisible();
  if (isMobile) {
    await page.getByRole("button", { name: "More", exact: true }).click();
    await expect(
      page
        .getByRole("dialog", { name: "More", exact: true })
        .getByRole("button", { name: "Accounts", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(
      page.getByRole("dialog", { name: "More", exact: true }),
    ).toHaveCount(0);
    const selected = page
      .getByRole("navigation", { name: "Account navigation", exact: true })
      .getByRole("button", { name: "Accounts", exact: true });
    await expect(selected).toHaveAttribute("aria-current", "page");
    await expect(selected).toBeFocused();
  }
});

test("the overflow menu cannot reveal forbidden account controls and expires with the session", async ({
  page,
  isMobile,
}) => {
  await login(page, "marketing@example.org");
  if (isMobile)
    await page.getByRole("button", { name: "More", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Accounts", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Roles", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Audit history", exact: true }),
  ).toHaveCount(0);
  expect((await page.request.get("/api/v1/users")).status()).toBe(403);
  const csrf = (await page.context().cookies()).find(
    (cookie) => cookie.name === "happy_csrf",
  )!.value;
  expect(
    (
      await page.request.post("/api/v1/auth/logout", {
        headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": csrf },
      })
    ).status(),
  ).toBe(204);
  await page.evaluate(() =>
    window.dispatchEvent(new Event("happy:auth-expired")),
  );
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "More", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("navigation", { name: "Account navigation", exact: true }),
  ).toHaveCount(0);
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
});
