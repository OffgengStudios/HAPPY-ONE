import { expect, test, Page } from "@playwright/test";
import { navigate, signOut } from "./navigation";

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

test("authorized staff can inspect integration operations", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Integration operations");
  await expect(
    page.getByRole("heading", { name: "Integration operations", exact: true }),
  ).toBeVisible();
  const response = page.waitForResponse(
    (result) =>
      result.url().endsWith("/api/v1/intake-operations") &&
      result.request().method() === "GET",
  );
  await page
    .getByRole("button", { name: "Refresh operations", exact: true })
    .click();
  const result = await response;
  expect(result.status()).toBe(200);
  expect(Array.isArray((await result.json()).items)).toBe(true);
  await expect(
    page
      .getByRole("region", { name: "Workspace content", exact: true })
      .getByRole("alert"),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("login errors are actionable and an account can sign out", async ({
  page,
}, info) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@example.org");
  await page.getByLabel("Password", { exact: true }).fill("incorrect password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toHaveText(
    "Email or password is incorrect.",
  );
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My Work" })).toBeVisible();
  await navigate(page, "Account security");
  await expect(
    page.getByRole("heading", { name: "Active sessions" }),
  ).toBeVisible();
  await expect(page.getByText("Browser (this device)")).toBeVisible();
  await page.screenshot({
    path: info.outputPath("security.png"),
    fullPage: true,
  });
  await signOut(page);
});

test("marketing receives its workspace and cannot call account administration", async ({
  page,
}, info) => {
  await login(page, "marketing@example.org");
  await expect(
    page.locator("aside").getByText("Marketing", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Accounts", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Roles", exact: true }),
  ).toHaveCount(0);
  const response = await page.request.get("/api/v1/users");
  expect(response.status()).toBe(403);
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("marketing.png"),
    fullPage: true,
  });
});

test("administrator creates an account, updates its status, and reads audit history", async ({
  page,
}, info) => {
  await login(page);
  await navigate(page, "Accounts");
  await page.getByRole("button", { name: "New account", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "New account" });
  const name = "Browser Staff " + info.project.name;
  await dialog.getByLabel("Full name").fill(name);
  await dialog
    .getByLabel("Email", { exact: true })
    .fill("browser-" + info.project.name + "@example.org");
  await dialog.getByLabel("Password", { exact: true }).fill(password!);
  await dialog.getByLabel("Supply", { exact: true }).check();
  await dialog.getByLabel("Primary role").selectOption({ label: "Supply" });
  await page.screenshot({
    path: info.outputPath("new-account.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "Save account" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit " + name, exact: true }).click();
  const editor = page.getByRole("dialog", { name: "Edit account" });
  await editor.getByLabel("Active account").uncheck();
  await editor.getByRole("button", { name: "Save account" }).click();
  await expect(editor).not.toBeVisible();
  await navigate(page, "Audit history");
  await expect(
    page.getByText("user.created", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("user.deactivated", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("Search audit history")
    .fill("readiness.synthetic_actor");
  await page.getByText("readiness.synthetic_actor", { exact: true }).click();
  await expect(
    page.getByText("INTEGRATION: HAMIS", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: info.outputPath("audit.png"), fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("administrator creates and edits a custom role", async ({
  page,
}, info) => {
  await login(page);
  await navigate(page, "Roles");
  await page.getByRole("button", { name: "New role", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "New role" });
  const name = "Browser Reviewer " + info.project.name;
  await dialog
    .getByLabel("Role code")
    .fill("REVIEWER_" + info.project.name.toUpperCase());
  await dialog.getByLabel("Role name").fill(name);
  await dialog
    .getByLabel("Description", { exact: true })
    .fill("Synthetic browser verification");
  await dialog.getByLabel("workspace_management:view", { exact: true }).check();
  await dialog.getByRole("button", { name: "Save role" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Edit " + name, exact: true }).click();
  const editor = page.getByRole("dialog", { name: "Edit role" });
  await editor.getByLabel("Role name").fill(name + " Updated");
  await editor.getByRole("button", { name: "Save role" }).click();
  await expect(editor).not.toBeVisible();
  await expect(
    page.getByText(name + " Updated", { exact: true }),
  ).toBeVisible();
});
