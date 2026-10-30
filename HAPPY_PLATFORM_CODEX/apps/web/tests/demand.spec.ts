import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page, email = "demand@example.org") {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Account navigation", exact: true }),
  ).toBeVisible();
}
async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}
async function relationship(page: Page, target: string) {
  await page
    .getByRole("button", { name: "Change status", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Change relationship status",
  });
  await dialog.getByLabel("Next status").selectOption(target);
  await save(page, "Change relationship status");
  await expect(
    page.getByRole("tabpanel").getByRole("heading", {
      name: target.replaceAll("_", " ").toLowerCase(),
      exact: true,
    }),
  ).toBeVisible();
}
async function vacancyStatus(page: Page, target: string) {
  await page
    .getByRole("button", { name: "Change status", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Change vacancy status" });
  await dialog.getByLabel("Next status").selectOption(target);
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic employer decision");
  if (target === "CLOSED")
    await dialog
      .getByRole("combobox", { name: "Closure reason", exact: true })
      .selectOption("EMPLOYER_CANCELLED");
  await save(page, "Change vacancy status");
}

test("Demand entry is internal and legacy employer routes stay unavailable", async ({
  page,
}) => {
  await login(page);
  await expect(
    page.getByRole("button", { name: "Employer Submissions", exact: true }),
  ).toHaveCount(0);
  await navigate(page, "Employers");
  await expect(
    page.getByRole("button", { name: "New employer", exact: true }),
  ).toBeVisible();
  for (const route of [
    "/api/v1/employer-intake/config",
    "/api/v1/integrations/employer-portal/submissions",
  ]) {
    const response = await page.request.get(route);
    expect(response.status()).toBe(404);
  }
});

test("Demand staff completes an employer-to-vacancy workflow", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  await page.getByRole("button", { name: "Employers", exact: true }).click();
  await page.getByRole("button", { name: "New employer", exact: true }).click();
  const employerName = "Browser Logistics " + info.project.name;
  const actionTitle = "Review new recruitment brief " + info.project.name;
  let dialog = page.getByRole("dialog", { name: "New employer" });
  await dialog.getByLabel("Employer name").fill(employerName);
  await dialog.getByLabel("Community", { exact: true }).fill("Accra");
  await expect(dialog.getByLabel("MOU required")).toBeChecked();
  await save(page, "New employer");
  await expect(
    page.getByRole("heading", { name: employerName, exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Contacts", exact: true }).click();
  await page.getByRole("button", { name: "New contact", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "New contact" });
  await dialog.getByLabel("Contact name").fill("Synthetic Hiring Lead");
  await dialog.getByLabel("Phone", { exact: true }).fill("0241234567");
  await dialog.getByLabel("Contact email").fill("hiring@example.org");
  await dialog.getByLabel("Primary contact").check();
  await save(page, "New contact");
  await expect(page.getByText("+233241234567", { exact: false })).toBeVisible();
  await page
    .getByRole("tab", { name: "Partnership / MOU", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Partnership history", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "New period", exact: true }),
  ).toBeVisible();
  for (const status of ["CONTACTED", "ENGAGED", "INTERESTED", "MOU_PENDING"])
    await relationship(page, status);
  await page
    .getByRole("button", { name: "Edit partnership", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Edit partnership" });
  await dialog.getByLabel("MOU sent (Ghana time)").fill("2026-10-01T09:00");
  await dialog.getByLabel("MOU signed (Ghana time)").fill("2026-10-02T09:00");
  await dialog
    .getByRole("combobox", { name: "Action priority", exact: true })
    .selectOption("URGENT");
  await dialog.getByLabel("Next action", { exact: true }).fill(actionTitle);
  await dialog
    .getByLabel("Due (Ghana time)", { exact: true })
    .fill("2026-10-03T09:00");
  await save(page, "Edit partnership");
  await relationship(page, "MOU_SIGNED");
  await relationship(page, "ACTIVE");
  await page.screenshot({
    path: info.outputPath("employer.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "New vacancy", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "New vacancy" });
  const vacancyName = "Browser Driver " + info.project.name;
  await dialog.getByLabel("Vacancy title").fill(vacancyName);
  await dialog.getByLabel("Positions required").fill("3");
  await dialog.getByLabel("Minimum salary").fill("1500");
  await dialog.getByLabel("Maximum salary").fill("2000");
  await dialog.getByLabel("Pay frequency").selectOption("MONTHLY");
  await save(page, "New vacancy");
  await expect(
    page.getByRole("heading", { name: vacancyName, exact: true }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Job descriptions", exact: true })
    .click();
  await expect(page.getByText("No document versions recorded")).toBeVisible();
  await expect(page.getByText("Upload version", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Requirements", exact: true }).click();
  await page
    .getByRole("button", { name: "New requirement", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "New requirement" });
  await dialog.getByLabel("Criterion type").fill("SKILL");
  await dialog.getByLabel("Criterion key").fill("manual_driving");
  await dialog.getByLabel("Value (JSON)").fill("true");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Employer specification");
  await save(page, "New requirement");
  await expect(page.getByText("manual_driving", { exact: true })).toBeVisible();
  await vacancyStatus(page, "PENDING_CONFIRMATION");
  await vacancyStatus(page, "ACTIVE");
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Edit vacancy" });
  await dialog.getByLabel("Positions required").fill("5");
  await dialog.getByLabel("Minimum salary").fill("1800");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Employer expanded recruitment");
  await save(page, "Edit vacancy");
  await page.getByRole("tab", { name: "Changes", exact: true }).click();
  await expect(
    page.getByText("Positions required", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Minimum salary", { exact: true })).toBeVisible();
  await page.screenshot({
    path: info.outputPath("vacancy-changes.png"),
    fullPage: true,
  });
  await vacancyStatus(page, "CLOSED");
  await page.getByRole("button", { name: "My Work", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Overdue", exact: true })
      .getByText(actionTitle, { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "High priority", exact: true })
      .getByText(actionTitle, { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Recently assigned", exact: true })
      .getByText(actionTitle, { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("my-work.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Demand Dashboard", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Active employers", exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("No pending MOUs", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("demand-dashboard.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Active employers", exact: false })
    .click();
  await expect(
    page.getByRole("heading", { name: "Employers", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Status filter")).toHaveValue("ACTIVE");
  await expect(
    page.getByRole("button", { name: employerName, exact: false }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("Marketing sees vacancies without employer contact or editing access", async ({
  page,
}, info) => {
  await login(page, "marketing@example.org");
  await expect(
    page.getByRole("button", { name: "Employers", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Vacancies", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Vacancies", exact: true }),
  ).toBeVisible();
  const response = await page.request.get("/api/v1/vacancies");
  expect(response.status()).toBe(200);
  const records = await response.json();
  expect(records.items.length).toBeGreaterThan(0);
  const id = records.items[0].id;
  expect((await page.request.get("/api/v1/organizations")).status()).toBe(403);
  expect(
    (
      await page.request.get(
        "/api/v1/organizations/" +
          records.items[0].organization_id +
          "/contacts",
      )
    ).status(),
  ).toBe(403);
  await page
    .getByRole("button", { name: records.items[0].title, exact: false })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Change status", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Employer", exact: true }),
  ).toHaveCount(0);
  expect(
    (await page.request.get("/api/v1/vacancies/" + id + "/headcount")).status(),
  ).toBe(200);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("vacancy-readonly.png"),
    fullPage: true,
  });
});
