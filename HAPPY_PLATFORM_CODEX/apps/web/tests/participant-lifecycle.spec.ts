import { test, expect, Page } from "@playwright/test";
import { appendFileSync } from "node:fs";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(
  !password,
  "Requires the isolated browser API or explicit local test runner.",
);

async function headers(page: Page) {
  const cookies = await page.context().cookies();
  return {
    Origin: new URL(page.url()).origin,
    "X-CSRF-Token": cookies.find((item) => item.name === "happy_csrf")!.value,
  };
}

test("participant lifecycle preserves independent IDs and event ages", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill(process.env.HAPPY_E2E_EMAIL ?? "admin@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Email", { exact: true })).toHaveCount(0);
  await navigate(page, "Participants");
  await page
    .getByRole("button", { name: "New participant", exact: true })
    .click();
  let dialog = page.getByRole("dialog", {
    name: "New participant",
    exact: true,
  });
  const suffix = `${info.project.name}-${Date.now()}`;
  await dialog
    .getByLabel("First name", { exact: true })
    .fill("SyntheticLifecycle");
  await dialog.getByLabel("Surname", { exact: true }).fill(suffix);
  await dialog
    .getByLabel("Phone", { exact: true })
    .fill("024" + String(Date.now()).slice(-7));
  await dialog
    .getByLabel("Community", { exact: true })
    .fill("Synthetic lifecycle verification");
  await dialog
    .getByLabel("Reviewed as a distinct participant", { exact: true })
    .check();
  await dialog
    .getByLabel("Onboarding Date", { exact: true })
    .fill("2026-01-02");
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/participants") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const participant = await response.json();
  if (process.env.HAPPY_LIFECYCLE_CREATED)
    appendFileSync(
      process.env.HAPPY_LIFECYCLE_CREATED,
      JSON.stringify({ participant: participant.id }) + "\n",
    );
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Complete onboarding", exact: true }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "Onboarding", exact: true }).click();
  await page
    .getByRole("button", { name: "Identity & inclusion", exact: true })
    .click();
  await page.getByRole("button", { name: "Demographics", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Edit demographics", exact: true });
  await dialog.getByLabel("Date of birth", { exact: true }).fill("2000-06-14");
  await expect(dialog.getByRole("status")).toHaveText("Saved");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  for (const kind of ["GHANA_CARD", "VOTER_ID"]) {
    await page
      .getByRole("button", { name: "Ghana Card / Voter’s ID", exact: true })
      .click();
    dialog = page.getByRole("dialog", { name: "Record identity", exact: true });
    await dialog
      .getByRole("combobox", { name: "Identity type", exact: true })
      .selectOption(kind);
    await dialog
      .getByLabel("Ghana Card / Voter’s ID Number", { exact: false })
      .fill(`SYNTHETIC-${kind.replaceAll("_", "-")}-${suffix}`);
    await dialog.getByRole("button", { name: "Save", exact: true }).click();
    await expect(dialog).toHaveCount(0);
  }
  const sensitive = await (
    await page.request.get(`/api/v1/participants/${participant.id}/sensitive`)
  ).json();
  expect(sensitive.has_ghana_card).toBe(true);
  expect(sensitive.has_voter_id).toBe(true);
  expect(sensitive.age_at_onboarding).toBe(25);
  await page.screenshot({
    path: info.outputPath("identity-and-age.png"),
    fullPage: true,
  });
  for (const start of ["2026-06-13", "2026-06-14"]) {
    const courseResponse = await page.request.post("/api/v1/trainings", {
      headers: await headers(page),
      data: {
        title: `Synthetic lifecycle ${suffix} ${start}`,
        training_type: "SOFT_SKILLS",
        trainer_type: "INTERNAL",
        mode: "IN_PERSON",
        start_date: start,
        modules_json: ["Soft Skills", "IT Skills"],
      },
    });
    expect(courseResponse.status()).toBe(201);
    const course = await courseResponse.json();
    if (process.env.HAPPY_LIFECYCLE_CREATED)
      appendFileSync(
        process.env.HAPPY_LIFECYCLE_CREATED,
        JSON.stringify({ training: course.id }) + "\n",
      );
    expect(
      (
        await page.request.post(`/api/v1/trainings/${course.id}/participants`, {
          headers: await headers(page),
          data: { participant_ids: [participant.id] },
        })
      ).status(),
    ).toBe(201);
  }
  await page
    .getByRole("tab", { name: "Capacity Building", exact: true })
    .click();
  await expect(page.getByRole("article")).toHaveCount(2);
  expect(
    (
      await (
        await page.request.get(
          `/api/v1/participants/${participant.id}/capacity-building`,
        )
      ).json()
    ).items
      .map(
        (item: { age_at_training_start: number }) => item.age_at_training_start,
      )
      .sort(),
  ).toEqual([25, 26]);
  await page
    .getByRole("button", { name: "Update attendance and modules", exact: true })
    .first()
    .click();
  dialog = page.getByRole("dialog", {
    name: "Update individual learning",
    exact: true,
  });
  await dialog
    .getByRole("combobox", { name: "Completion Status", exact: true })
    .selectOption("COMPLETED");
  await dialog
    .getByLabel("Modules received (one per line)", { exact: true })
    .fill("Soft Skills");
  await dialog
    .getByLabel("Modules completed (one per line)", { exact: true })
    .fill("Soft Skills");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("capacity-building.png"),
    fullPage: true,
  });
  await page
    .getByRole("tab", { name: "Placements & Employment", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Record verified employment outcome",
      exact: true,
    })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Record verified employment outcome",
    exact: true,
  });
  await dialog
    .getByLabel("Employment Start Date", { exact: true })
    .fill("2026-07-01");
  await dialog
    .getByLabel("Observation Date", { exact: true })
    .fill("2026-08-01");
  await dialog
    .getByRole("combobox", { name: "Employment Type", exact: true })
    .selectOption("SELF");
  await dialog
    .getByRole("combobox", { name: "Employment Category", exact: true })
    .selectOption("NEW");
  await dialog
    .getByLabel("Verification evidence and notes", { exact: true })
    .fill("Synthetic lifecycle verification only");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("SELF", { exact: true })).toBeVisible();
  expect(
    (
      await (
        await page.request.get(
          `/api/v1/participants/${participant.id}/employment-outcomes`,
        )
      ).json()
    ).items[0].placement_id,
  ).toBeNull();
  await page.screenshot({
    path: info.outputPath("employment-outcomes.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const workspace = page.getByRole("combobox", {
    name: "Workspace",
    exact: true,
  });
  if (await workspace.isVisible()) await workspace.selectOption("MANAGEMENT");
  await navigate(page, "Reports & Targets");
  await expect(
    page.getByRole("heading", {
      name: "Programme lifecycle report",
      exact: true,
    }),
  ).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download programme workbook", exact: true })
    .click();
  expect((await downloaded).suggestedFilename()).toBe("happy-programme.xlsx");
  expect(errors).toEqual([]);
});
