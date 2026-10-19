import { expect, type Locator, type Page, test } from "@playwright/test";
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
async function mobile(page: Page) {
  await page.setViewportSize({ width: 412, height: 915 });
}
async function csrf(page: Page) {
  return {
    Origin: new URL(page.url()).origin,
    "X-CSRF-Token": (await page.context().cookies()).find(
      (cookie) => cookie.name === "happy_csrf",
    )!.value,
  };
}
async function quickCreate(page: Page, name: string, choose = false) {
  await page.getByRole("button", { name: "Quick add", exact: true }).click();
  if (choose)
    await page
      .getByRole("dialog", { name: "Quick add", exact: true })
      .getByRole("button", { name, exact: true })
      .click();
  const dialog = page.getByRole("dialog", { name, exact: true });
  await expect(dialog).toBeVisible();
  return dialog;
}
async function frame(page: Page, dialog: Locator, fullscreen: boolean) {
  await expect(dialog).toBeVisible();
  await dialog.evaluate(async (element) => {
    await Promise.all(
      element
        .getAnimations()
        .map((animation) => animation.finished.catch(() => {})),
    );
  });
  const box = (await dialog.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(Math.abs(box.y)).toBeLessThan(2);
  expect(Math.abs(box.height - viewport.height)).toBeLessThan(2);
  expect(Math.abs(box.x + box.width - viewport.width)).toBeLessThan(2);
  if (fullscreen) expect(Math.abs(box.width - viewport.width)).toBeLessThan(2);
  else expect(box.width).toBeLessThanOrEqual(576);
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
}
async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

test("action editors use desktop drawers and mobile full-screen panels with reachable controls", async ({
  page,
  isMobile,
}, info) => {
  await login(page, "demand@example.org");
  await navigate(page, "Employers");
  await page.getByRole("button", { name: "New employer", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "New employer",
    exact: true,
  });
  await frame(page, dialog, isMobile);
  await expect(
    dialog.getByRole("button", { name: "Close", exact: true }),
  ).toBeInViewport();
  await expect(
    dialog.getByRole("button", { name: "Save", exact: true }),
  ).toBeInViewport();
  await dialog
    .getByLabel("Employer name", { exact: true })
    .fill("Draft retained across resize");
  await dialog.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(
    dialog.getByRole("button", { name: "Close", exact: true }),
  ).toBeInViewport();
  await expect(
    dialog.getByRole("button", { name: "Save", exact: true }),
  ).toBeInViewport();
  await page.screenshot({ path: info.outputPath("action-drawer.png") });
  await page.setViewportSize({ width: 320, height: 700 });
  await frame(page, dialog, true);
  await expect(dialog.getByLabel("Employer name", { exact: true })).toHaveValue(
    "Draft retained across resize",
  );
  await page.screenshot({ path: info.outputPath("action-narrow.png") });
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("Supply quick-add creates through the existing participant API and cannot expose Demand commands", async ({
  page,
}, info) => {
  await login(page, "supply@example.org");
  await mobile(page);
  const trigger = page.getByRole("button", { name: "Quick add", exact: true });
  await expect(trigger).toHaveAttribute("title", "New participant");
  const nav = (await page
    .getByRole("navigation", { name: "Account navigation", exact: true })
    .boundingBox())!;
  const button = (await trigger.boundingBox())!;
  expect(button.y + button.height).toBeLessThan(nav.y);
  const dialog = await quickCreate(page, "New participant");
  await frame(page, dialog, true);
  const user = await (await page.request.get("/api/v1/auth/me")).json();
  await expect(
    dialog.getByRole("combobox", { name: "Assigned owner", exact: true }),
  ).toHaveValue(user.id);
  await dialog.getByLabel("First name", { exact: true }).fill("Quickadd");
  await dialog
    .getByLabel("Surname", { exact: true })
    .fill("Intake " + info.project.name);
  await dialog
    .getByLabel("Phone", { exact: true })
    .fill(info.project.name === "mobile" ? "0249100002" : "0249100001");
  await dialog
    .getByLabel("Community", { exact: true })
    .fill("Synthetic quickadd " + info.project.name);
  await dialog.getByLabel("Reviewed as a distinct participant").check();
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/participants") &&
      response.request().method() === "POST",
  );
  await save(page, "New participant");
  const response = await created;
  expect(response.status()).toBe(201);
  const row = await response.json();
  await expect(
    page.getByRole("heading", { name: row.full_name, exact: true }),
  ).toBeVisible();
  expect(row.source_system).toBe("INTERNAL");
  expect(row.created_via).toBe("STAFF");
  expect(
    (
      await page.request.post("/api/v1/organizations", {
        headers: await csrf(page),
        data: { name: "Forbidden quickadd", organization_type: "EMPLOYER" },
      })
    ).status(),
  ).toBe(403);
  await page.screenshot({ path: info.outputPath("quickadd-participant.png") });
});

test("explicit grants allow creation outside default workspaces without assigning ineligible owners", async ({
  page,
}, info) => {
  await login(page, "granted-creator@example.org");
  await mobile(page);
  let dialog = await quickCreate(page, "New participant", true);
  await expect(
    dialog.getByRole("combobox", { name: "Assigned owner", exact: true }),
  ).toHaveValue("");
  await dialog.getByLabel("First name", { exact: true }).fill("Granted");
  await dialog
    .getByLabel("Surname", { exact: true })
    .fill("Creator " + info.project.name);
  await dialog
    .getByLabel("Phone", { exact: true })
    .fill(info.project.name === "mobile" ? "0249200002" : "0249200001");
  await dialog
    .getByLabel("Community", { exact: true })
    .fill("Synthetic grant " + info.project.name);
  await dialog.getByLabel("Reviewed as a distinct participant").check();
  const intake = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/participants") &&
      response.request().method() === "POST",
  );
  await save(page, "New participant");
  const participant = await (await intake).json();
  expect(participant.assigned_user_id).toBeNull();
  await expect(
    page.getByRole("heading", { name: participant.full_name, exact: true }),
  ).toBeVisible();
  dialog = await quickCreate(page, "New employer", true);
  await expect(
    dialog.getByRole("combobox", { name: "Relationship owner", exact: true }),
  ).toHaveValue("");
  await dialog
    .getByLabel("Employer name", { exact: true })
    .fill("Granted Employer " + info.project.name);
  await dialog.getByLabel("Distinct employer despite matching name").check();
  const employer = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/organizations") &&
      response.request().method() === "POST",
  );
  await save(page, "New employer");
  const response = await employer;
  expect(response.status()).toBe(201);
  const row = await response.json();
  expect(row.relationship_owner_id).toBeNull();
  await expect(
    page.getByRole("heading", { name: row.name, exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("aside").getByText("Marketing", { exact: true }),
  ).toBeVisible();
  expect((await page.request.get("/api/v1/users")).status()).toBe(403);
});

test("a Supply creator denied editing waits for owners and creates without ineligible self-assignment", async ({
  page,
}, info) => {
  await page.route("**/api/v1/supply/owners", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "Synthetic owner failure." } }),
    }),
  );
  await login(page, "supply-edit-denied@example.org");
  const user = await (await page.request.get("/api/v1/auth/me")).json();
  expect(user.permissions).toContain("participant:create");
  expect(user.permissions).not.toContain("participant:edit");
  await navigate(page, "Participants");
  await page
    .getByRole("button", { name: "New participant", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "New participant",
    exact: true,
  });
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByRole("region", { name: "Workspace content", exact: true })
      .getByRole("alert"),
  ).toHaveText("Staff options unavailable.");
  await page.unroute("**/api/v1/supply/owners");
  await page
    .getByRole("button", { name: "Retry staff options", exact: true })
    .click();
  await expect(dialog).toBeVisible();
  const owner = dialog.getByRole("combobox", {
    name: "Assigned owner",
    exact: true,
  });
  await expect(owner).toHaveValue("");
  await expect(owner.locator(`option[value="${user.id}"]`)).toHaveCount(0);
  await dialog.getByLabel("First name", { exact: true }).fill("Permission");
  await dialog
    .getByLabel("Surname", { exact: true })
    .fill("Intake " + info.project.name);
  await dialog
    .getByLabel("Phone", { exact: true })
    .fill(info.project.name === "mobile" ? "0249300002" : "0249300001");
  await dialog
    .getByLabel("Community", { exact: true })
    .fill("Synthetic owner regression");
  await dialog.getByLabel("Reviewed as a distinct participant").check();
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/participants") &&
      response.request().method() === "POST",
  );
  await save(page, "New participant");
  const response = await created;
  expect(response.request().postDataJSON().assigned_user_id).toBeNull();
  expect(response.status()).toBe(201);
  const participant = await response.json();
  expect(participant.assigned_user_id).toBeNull();
  await expect(
    page.getByRole("heading", { name: participant.full_name, exact: true }),
  ).toBeVisible();
  expect(
    (
      await page.request.patch("/api/v1/participants/" + participant.id, {
        headers: await csrf(page),
        data: { version: participant.version, assigned_user_id: user.id },
      })
    ).status(),
  ).toBe(403);
  await mobile(page);
  const quick = await quickCreate(page, "New participant");
  await expect(
    quick.getByRole("combobox", { name: "Assigned owner", exact: true }),
  ).toHaveValue("");
  await quick.getByRole("button", { name: "Cancel", exact: true }).click();
});

test("a DENY override removes employer quick-add while the vacancy flow remains authorized", async ({
  page,
}, info) => {
  await login(page, "demand-create-denied@example.org");
  await mobile(page);
  await expect(
    page.getByRole("button", { name: "Quick add", exact: true }),
  ).toHaveAttribute("title", "New vacancy");
  const dialog = await quickCreate(page, "New vacancy");
  await dialog
    .getByRole("combobox", { name: "Employer", exact: true })
    .selectOption({ label: "Synthetic Browser Employer" });
  await dialog
    .getByLabel("Vacancy title", { exact: true })
    .fill("Quickadd Vacancy " + info.project.name);
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/vacancies") &&
      response.request().method() === "POST",
  );
  await save(page, "New vacancy");
  expect((await created).status()).toBe(201);
  await expect(
    page.getByRole("heading", {
      name: "Quickadd Vacancy " + info.project.name,
      exact: true,
    }),
  ).toBeVisible();
  expect(
    (
      await page.request.post("/api/v1/organizations", {
        headers: await csrf(page),
        data: { name: "Denied command", organization_type: "EMPLOYER" },
      })
    ).status(),
  ).toBe(403);
  await signOut(page);
  await login(page, "marketing@example.org");
  await expect(
    page.getByRole("button", { name: "Quick add", exact: true }),
  ).toHaveCount(0);
});

test("quick-add waits for reference data, retries failures and never reopens a cancelled form", async ({
  page,
}) => {
  await page.route("**/api/v1/supply/owners", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { message: "Synthetic reference failure." },
      }),
    }),
  );
  await login(page, "supply@example.org");
  await mobile(page);
  await page.getByRole("button", { name: "Quick add", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Workspace content", exact: true })
      .getByRole("alert"),
  ).toHaveText("Staff options unavailable.");
  await expect(
    page.getByRole("dialog", { name: "New participant", exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/api/v1/supply/owners");
  await page
    .getByRole("button", { name: "Retry staff options", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "New participant",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByLabel("First name", { exact: true })
    .fill("Unsubmitted draft");
  await page.setViewportSize({ width: 1200, height: 800 });
  await frame(page, dialog, false);
  await expect(dialog.getByLabel("First name", { exact: true })).toHaveValue(
    "Unsubmitted draft",
  );
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Workspace content", exact: true }),
  ).toBeFocused();
  await mobile(page);
  await quickCreate(page, "New participant");
  await expect(dialog.getByLabel("First name", { exact: true })).toHaveValue(
    "",
  );
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Quick add", exact: true }),
  ).toBeFocused();
});

test("quick-add ordering follows workspace while resize and expired sessions clear its sheet", async ({
  page,
}, info) => {
  await login(page);
  await mobile(page);
  const trigger = page.getByRole("button", { name: "Quick add", exact: true });
  const sheet = page.getByRole("dialog", { name: "Quick add", exact: true });
  await trigger.click();
  expect(
    await sheet.getByRole("button", { name: /^New / }).allTextContents(),
  ).toEqual(["New employer", "New vacancy", "New participant"]);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption("SUPPLY");
  await trigger.click();
  expect(
    await sheet.getByRole("button", { name: /^New / }).allTextContents(),
  ).toEqual(["New participant", "New employer", "New vacancy"]);
  await page.screenshot({ path: info.outputPath("quickadd-sheet.png") });
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(sheet).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Workspace content", exact: true }),
  ).toBeFocused();
  await expect(trigger).toHaveCount(0);
  await mobile(page);
  await trigger.click();
  expect(
    (
      await page.request.post("/api/v1/auth/logout", {
        headers: await csrf(page),
      })
    ).status(),
  ).toBe(204);
  await page.evaluate(() =>
    window.dispatchEvent(new Event("happy:auth-expired")),
  );
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(sheet).toHaveCount(0);
  await expect(trigger).toHaveCount(0);
});
