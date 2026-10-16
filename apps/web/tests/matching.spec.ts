import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("matching@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My Work", exact: true }),
  ).toBeVisible();
}

async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

test("Matching staff qualifies, submits, interviews and selects a candidate", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  await navigate(page, "Pipeline");
  await expect(
    page.getByRole("heading", { name: "Candidate Pipeline", exact: true }),
  ).toBeVisible();
  const candidate = page.getByRole("button", {
    name: "Ama Matching Fixture " + info.project.name,
    exact: false,
  });
  await expect(candidate).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) >= 768)
    await expect(
      page.getByRole("region", { name: "Potential match", exact: true }),
    ).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) >= 768)
    await page.getByRole("button", { name: "List view", exact: true }).click();
  await page
    .getByRole("checkbox", {
      name: "Select Ama Matching Fixture " + info.project.name,
      exact: false,
    })
    .check();
  await page
    .getByRole("combobox", { name: "Bulk destination", exact: true })
    .selectOption("RECRUITER_REVIEW");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: "Bulk destination", exact: true }),
  ).toHaveCount(0);
  await expect(candidate).toBeVisible();
  await candidate.first().click();

  await page.getByRole("button", { name: "Pre screen", exact: true }).click();
  await save(page, "Pre screen");
  await page.getByRole("button", { name: "Pre-screen", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Record pre-screen" });
  await dialog.getByLabel("Salary accepted", { exact: true }).check();
  await dialog.getByLabel("Location accepted", { exact: true }).check();
  await dialog
    .getByLabel("Screening notes", { exact: true })
    .fill("Synthetic human review");
  await save(page, "Record pre-screen");
  await expect(
    page.getByText("Synthetic human review", { exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await save(page, "Submit to employer");
  await expect(
    page.getByText("Submitted", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Schedule", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Schedule interview" });
  await dialog
    .getByRole("combobox", { name: "Format", exact: true })
    .selectOption("VIDEO");
  await dialog
    .getByLabel("Date and time (Ghana time)")
    .fill("2026-10-12T10:00");
  await dialog
    .getByLabel("Location or link", { exact: true })
    .fill("https://meet.example.test/browser");
  await save(page, "Schedule interview");

  await navigate(page, "Interviews");
  await page.getByLabel("Interview date", { exact: true }).fill("2026-10-12");
  const interview = page.getByText(
    "Ama Matching Fixture " + info.project.name,
    { exact: false },
  );
  await expect(interview).toBeVisible();
  await page.getByRole("button", { name: "Reschedule", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Reschedule" });
  await dialog
    .getByLabel("New date and time (Ghana time)", { exact: true })
    .fill("2026-10-13T10:00");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Employer requested a new day");
  await save(page, "Reschedule");
  await page.getByLabel("Interview date", { exact: true }).fill("2026-10-13");
  await expect(interview).toBeVisible();
  await page.getByRole("button", { name: "Attended", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Attend" });
  await dialog
    .getByLabel("Attendance note", { exact: true })
    .fill("Candidate attended");
  await save(page, "Attend");
  await page
    .getByRole("button", { name: "Record outcome", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Outcome" });
  await dialog
    .getByRole("combobox", { name: "Outcome", exact: true })
    .selectOption("PASSED");
  await dialog
    .getByLabel("Outcome note", { exact: true })
    .fill("Passed interview");
  await save(page, "Outcome");

  await page
    .getByText("Ama Matching Fixture " + info.project.name, { exact: false })
    .first()
    .click();
  await page.getByRole("button", { name: "Decision", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Employer decision" });
  await dialog
    .getByRole("combobox", { name: "Decision", exact: true })
    .selectOption("SELECTED");
  await dialog
    .getByLabel("Decision reason", { exact: true })
    .fill("Employer selected candidate");
  await save(page, "Employer decision");
  await expect(
    page.getByText("Selected", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("matching-selected.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
