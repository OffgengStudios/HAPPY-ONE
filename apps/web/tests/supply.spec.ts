import { expect, Page, test } from "@playwright/test";
import { navigate } from "./navigation";

const password = process.env.HAPPY_E2E_PASSWORD;
test.skip(!password, "Run pnpm verify with the isolated browser API.");
async function login(page: Page, email = "supply@example.org") {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My Work", exact: true }),
  ).toBeVisible();
}
async function save(page: Page, title: string) {
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog.getByRole("button", { name: /^Save(?: draft)?$/ }).click();
  await expect(dialog).toHaveCount(0);
}
async function csrf(page: Page) {
  return {
    Origin: new URL(page.url()).origin,
    "X-CSRF-Token": (await page.context().cookies()).find(
      (cookie) => cookie.name === "happy_csrf",
    )!.value,
  };
}
async function newDraft(page: Page, suffix: string) {
  const response = await page.request.post("/api/v1/participants", {
    headers: await csrf(page),
    data: {
      first_name: "Draft",
      surname: suffix,
      phone_raw: "024" + String(Date.now()).slice(-7),
      community: "Synthetic " + suffix,
    },
  });
  expect(response.status()).toBe(201);
  const row = await response.json();
  await navigate(page, "Participants");
  await page.getByLabel("Search", { exact: true }).fill(row.full_name);
  await page.getByRole("button", { name: row.full_name, exact: false }).click();
  return row;
}
function sectionSaved(page: Page, id: string, section: string) {
  return page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith("/participants/" + id + "/onboarding/" + section) &&
      response.request().method() === "PATCH",
  );
}

test("onboarding autosave queues in-flight edits and recovers an offline draft", async ({
  page,
}, info) => {
  await login(page);
  const row = await newDraft(page, "Autosave " + info.project.name);
  await page.getByRole("tab", { name: "Basic", exact: true }).click();
  await page.getByRole("button", { name: "Edit basic", exact: true }).click();
  let dialog = page.getByRole("dialog", {
    name: "Edit basic details",
    exact: true,
  });
  let saves = 0;
  let firstStarted!: () => void;
  let release!: () => void;
  const started = new Promise<void>((resolve) => {
    firstStarted = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/participants/" + row.id + "/onboarding/basic",
    async (route) => {
      if (route.request().method() === "PATCH") {
        saves++;
        if (saves === 1) {
          firstStarted();
          await released;
        }
      }
      await route.continue();
    },
  );
  await dialog
    .getByLabel("Other names", { exact: true })
    .fill("First revision");
  await started;
  await expect(dialog.getByRole("status")).toHaveText("Saving...");
  await dialog
    .getByLabel("Other names", { exact: true })
    .fill("Latest revision");
  release();
  await expect.poll(() => saves).toBe(2);
  await expect(dialog.getByRole("status")).toHaveText("Saved");
  let persisted = await (
    await page.request.get("/api/v1/participants/" + row.id)
  ).json();
  expect(persisted.other_names).toBe("Latest revision");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("tab", { name: "Contact", exact: true }).click();
  await page.getByRole("button", { name: "Edit contact", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Edit contact", exact: true });
  await page.context().setOffline(true);
  await dialog
    .getByLabel("Directions", { exact: true })
    .fill("Offline draft retained in memory");
  await expect(dialog.getByRole("status")).toHaveText(
    "Offline - changes not saved",
  );
  await expect(
    dialog.getByRole("button", { name: "Save draft", exact: true }),
  ).toBeDisabled();
  const recovered = sectionSaved(page, row.id, "contact");
  await page.context().setOffline(false);
  expect((await recovered).status()).toBe(200);
  await expect(dialog.getByRole("status")).toHaveText("Saved");
  persisted = await (
    await page.request.get("/api/v1/participants/" + row.id)
  ).json();
  expect(persisted.directions).toBe("Offline draft retained in memory");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("tab", { name: "Education", exact: true }).click();
  await page
    .getByRole("button", { name: "Edit education", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Edit education", exact: true });
  await dialog
    .getByRole("button", { name: "Add qualification", exact: true })
    .click();
  const educationSaved = sectionSaved(page, row.id, "education");
  await dialog
    .getByLabel("Education level", { exact: true })
    .fill("Synthetic qualification");
  expect((await educationSaved).status()).toBe(200);
  await expect(dialog.getByRole("status")).toHaveText("Saved");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await expect(
    page.getByText("Synthetic qualification", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("onboarding-autosave.png"),
    fullPage: true,
  });
});

test("draft validation retains edits and a version conflict cannot overwrite another editor", async ({
  page,
}, info) => {
  await login(page);
  const row = await newDraft(page, "Conflict " + info.project.name);
  await page.getByRole("tab", { name: "Contact", exact: true }).click();
  await page.getByRole("button", { name: "Edit contact", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Edit contact", exact: true });
  const invalid = sectionSaved(page, row.id, "contact");
  await dialog.getByLabel("Phone", { exact: true }).fill("invalid telephone");
  expect((await invalid).status()).toBe(422);
  await expect(dialog.getByRole("alert")).toBeVisible();
  page.once("dialog", (confirmation) => void confirmation.dismiss());
  await dialog.getByLabel("Phone", { exact: true }).press("Escape");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Phone", { exact: true })).toHaveValue(
    "invalid telephone",
  );
  const fixed = sectionSaved(page, row.id, "contact");
  await dialog.getByLabel("Phone", { exact: true }).fill(row.phone_raw);
  await dialog
    .getByLabel("Directions", { exact: true })
    .fill("Corrected draft");
  expect((await fixed).status()).toBe(200);
  await expect(dialog.getByRole("status")).toHaveText("Saved");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("tab", { name: "Basic", exact: true }).click();
  await page.getByRole("button", { name: "Edit basic", exact: true }).click();
  dialog = page.getByRole("dialog", {
    name: "Edit basic details",
    exact: true,
  });
  const latest = await (
    await page.request.get("/api/v1/participants/" + row.id)
  ).json();
  const otherEditor = await page.request.patch(
    "/api/v1/participants/" + row.id + "/onboarding/basic",
    {
      headers: await csrf(page),
      data: {
        version: latest.version,
        first_name: row.first_name,
        surname: row.surname,
        other_names: "Other editor's approved value",
      },
    },
  );
  expect(otherEditor.status()).toBe(200);
  const conflicted = sectionSaved(page, row.id, "basic");
  await dialog
    .getByLabel("Other names", { exact: true })
    .fill("Stale local edit");
  expect((await conflicted).status()).toBe(409);
  await expect(dialog.getByRole("status")).toHaveText(
    "Record changed - review required",
  );
  await expect(dialog.getByLabel("Other names", { exact: true })).toHaveValue(
    "Stale local edit",
  );
  await expect(
    dialog.getByRole("button", { name: "Save draft", exact: true }),
  ).toBeDisabled();
  const persisted = await (
    await page.request.get("/api/v1/participants/" + row.id)
  ).json();
  expect(persisted.other_names).toBe("Other editor's approved value");
  await page.screenshot({
    path: info.outputPath("onboarding-conflict.png"),
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "Review latest record", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByText("Other editor's approved value", { exact: true }),
  ).toBeVisible();
});

test("a denied participant permission shows an actionable Supply access state", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill("supply-denied@example.org");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Participant access is not permitted. Contact an administrator.",
  );
  await expect(
    page.getByRole("button", { name: "Participants", exact: true }),
  ).toHaveCount(0);
  expect((await page.request.get("/api/v1/participants")).status()).toBe(403);
  expect((await page.request.get("/api/v1/supply/my-work")).status()).toBe(403);
});

test("private CV approval and download preserve the current version when a new scan is pending", async ({
  page,
}, info) => {
  await login(page);
  await page.getByRole("button", { name: "Participants", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Search", exact: true })
    .fill("Synthetic CV Fixture " + info.project.name);
  await page
    .getByRole("button", {
      name: "Synthetic CV Fixture " + info.project.name,
      exact: false,
    })
    .click();
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  const participant = (
    await (
      await page.request.get(
        "/api/v1/participants?q=" +
          encodeURIComponent("Synthetic CV Fixture " + info.project.name),
      )
    ).json()
  ).items[0];
  let versions = (
    await (
      await page.request.get(
        "/api/v1/participants/" + participant.id + "/cv/versions",
      )
    ).json()
  ).items;
  const available = versions.find(
    (item: { scan_status: string }) => item.scan_status === "AVAILABLE",
  );
  expect(available).toBeTruthy();
  // A seeded AVAILABLE fixture exercises UI approval, not real scanner acceptance.
  await page.getByRole("button", { name: "Approve CV", exact: true }).click();
  await expect(page.getByText(/Current approved CV/)).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download CV version 1", exact: true })
    .click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("cv-1.pdf");
  expect(await download.failure()).toBeNull();
  const fixtureBytes = await (
    await page.request.get("/api/v1/files/" + available.id + "/download")
  ).body();
  await page.getByRole("button", { name: "Upload CV", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Upload CV", exact: true });
  await dialog.getByLabel("CV document", { exact: true }).setInputFiles({
    name: "pending-" + info.project.name + ".pdf",
    mimeType: "application/pdf",
    buffer: fixtureBytes,
  });
  await dialog.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText(/Version \d+ \| scanning/)).toBeVisible();
  const current = await (
    await page.request.get("/api/v1/participants/" + participant.id)
  ).json();
  expect(current.current_cv_id).toBe(available.id);
  expect(current.cv_status).toBe("READY");
  versions = (
    await (
      await page.request.get(
        "/api/v1/participants/" + participant.id + "/cv/versions",
      )
    ).json()
  ).items;
  const pending = versions.find(
    (item: { original_filename: string }) =>
      item.original_filename === "pending-" + info.project.name + ".pdf",
  );
  expect(pending.scan_status).toBe("SCANNING");
  expect(pending).not.toHaveProperty("storage_key");
  expect(pending).not.toHaveProperty("sha256");
  expect(
    (
      await page.request.get("/api/v1/files/" + pending.id + "/download")
    ).status(),
  ).toBe(409);
  expect(
    (
      await page.request.post("/api/v1/cv/" + pending.id + "/approve", {
        headers: await csrf(page),
        data: { version: current.version },
      })
    ).status(),
  ).toBe(409);
  const rescanned = page.waitForResponse(
    (response) =>
      response.url().endsWith("/files/" + pending.id + "/rescan") &&
      response.request().method() === "POST",
  );
  const refreshed = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith("/participants/" + participant.id + "/onboarding") &&
      response.request().method() === "GET",
  );
  await page.getByRole("button", { name: "Rescan", exact: true }).click();
  expect((await rescanned).status()).toBe(200);
  await (await refreshed).json();
  await expect(page.getByText(/Version \d+ \| scanning/)).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Download CV version " + pending.version_number,
      exact: true,
    }),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("cv-private-versions.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Archive CV version " + pending.version_number,
      exact: true,
    })
    .click();
  dialog = page.getByRole("dialog", { name: "Archive CV", exact: true });
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic superseded upload");
  await save(page, "Archive CV");
  await expect(page.getByText(/Version \d+ \| archived/)).toBeVisible();
  const after = await (
    await page.request.get("/api/v1/participants/" + participant.id)
  ).json();
  expect(after.current_cv_id).toBe(available.id);
  const activity = (
    await (
      await page.request.get(
        "/api/v1/participants/" + participant.id + "/activity?limit=100",
      )
    ).json()
  ).items;
  expect(
    activity.map((item: { event_code: string }) => item.event_code),
  ).toEqual(
    expect.arrayContaining([
      "cv.approved",
      "document.downloaded_sensitive",
      "document.uploaded",
      "document.scan_completed",
      "document.archived",
    ]),
  );
  for (const section of ["Basic", "Contact"]) {
    await page.getByRole("tab", { name: section, exact: true }).click();
    await page
      .getByRole("button", {
        name: "Edit " + section.toLowerCase(),
        exact: true,
      })
      .click();
    await save(
      page,
      section === "Basic" ? "Edit basic details" : "Edit contact",
    );
  }
  await page.getByRole("tab", { name: "Consent", exact: true }).click();
  await page
    .getByRole("button", { name: "Record consent", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Record consent", exact: true });
  await dialog.getByLabel("Consented (Ghana time)").fill("2026-10-01T09:00");
  await dialog.getByLabel("Participant agreed to the recorded notice").check();
  await save(page, "Record consent");
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  await page
    .getByRole("button", { name: "Record review", exact: true })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Review participant",
    exact: true,
  });
  await dialog.getByLabel("Profile reviewed by staff").check();
  await save(page, "Review participant");
  await page
    .getByRole("button", { name: "Complete onboarding", exact: true })
    .click();
  await save(page, "Complete onboarding");
  await page
    .getByRole("button", { name: "Assess readiness", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Assess readiness", exact: true });
  await dialog
    .getByRole("combobox", { name: "Readiness", exact: true })
    .selectOption("JOB_READY");
  await dialog
    .getByRole("combobox", { name: "Availability", exact: true })
    .selectOption("AVAILABLE");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic reviewed CV and onboarding");
  await save(page, "Assess readiness");
  await expect(page.getByText("Eligible", { exact: true })).toBeVisible();
  const ready = await (
    await page.request.get("/api/v1/participants/" + participant.id)
  ).json();
  expect(ready.onboarding_status).toBe("COMPLETE");
  expect(ready.cv_status).toBe("READY");
  expect(ready.readiness_status).toBe("JOB_READY");
  expect(ready.submission_eligible).toBe(true);
  await page.screenshot({
    path: info.outputPath("cv-ready-onboarding.png"),
    fullPage: true,
  });
});
test("Supply staff completes progressive onboarding and withdraws consent", async ({
  page,
}, info) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  await page.getByRole("button", { name: "Participants", exact: true }).click();
  await page
    .getByRole("button", { name: "New participant", exact: true })
    .click();
  let dialog = page.getByRole("dialog", {
    name: "New participant",
    exact: true,
  });
  const name = "Browser Supply " + info.project.name;
  await dialog.getByLabel("First name", { exact: true }).fill("Browser");
  await dialog
    .getByLabel("Surname", { exact: true })
    .fill("Supply " + info.project.name);
  await dialog
    .getByLabel("Phone", { exact: true })
    .fill(info.project.name === "mobile" ? "0247654321" : "0241234567");
  await dialog
    .getByLabel("Community", { exact: true })
    .fill("Accra " + info.project.name);
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/participants") &&
      response.request().method() === "POST",
  );
  await save(page, "New participant");
  const participantId = (await (await created).json()).id;
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Call", exact: true }),
  ).toHaveAttribute(
    "href",
    info.project.name === "mobile" ? "tel:+233247654321" : "tel:+233241234567",
  );
  await expect(
    page.getByRole("button", { name: "Complete onboarding", exact: true }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "Education", exact: true }).click();
  await page
    .getByRole("button", { name: "Edit education", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Edit education" });
  await dialog.getByRole("button", { name: "Add qualification" }).click();
  await dialog.getByLabel("Education level").fill("Secondary");
  await dialog
    .getByLabel("Institution", { exact: true })
    .fill("Synthetic School");
  await dialog.getByLabel("Highest qualification").check();
  await save(page, "Edit education");
  await expect(
    page.getByText("Synthetic School", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Employment", exact: true }).click();
  await page
    .getByRole("button", { name: "Edit employment", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Edit employment" });
  await dialog
    .getByLabel("Employment status", { exact: true })
    .fill("Seeking work");
  await dialog.getByRole("button", { name: "Add skill", exact: true }).click();
  await dialog.getByLabel("Skill", { exact: true }).fill("Customer service");
  await save(page, "Edit employment");
  await expect(
    page.getByText("Customer service", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Consent", exact: true }).click();
  await page
    .getByRole("button", { name: "Record consent", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Record consent" });
  await dialog.getByLabel("Consented (Ghana time)").fill("2026-10-01T09:00");
  await expect(dialog.getByLabel("Privacy notice version")).toHaveValue(
    "SYNTHETIC-E2E-NOTICE",
  );
  await dialog.getByLabel("Participant agreed to the recorded notice").check();
  await save(page, "Record consent");
  await expect(
    page.getByText("programme consent", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  await page
    .getByRole("button", { name: "Record review", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Review participant" });
  await dialog.getByLabel("Profile reviewed by staff").check();
  await save(page, "Review participant");
  await page
    .getByRole("button", { name: "Complete onboarding", exact: true })
    .click();
  await save(page, "Complete onboarding");
  await expect(page.getByText("Eligible", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Staff-assisted onboarding", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Assess readiness", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Assess readiness" });
  await dialog
    .getByRole("combobox", { name: "Readiness", exact: true })
    .selectOption("JOB_READY");
  await dialog
    .getByRole("combobox", { name: "Availability", exact: true })
    .selectOption("AVAILABLE");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic staff assessment");
  let refreshStarted!: () => void;
  let releaseRefresh!: () => void;
  const refreshPending = new Promise<void>((resolve) => {
    refreshStarted = resolve;
  });
  const refreshReleased = new Promise<void>((resolve) => {
    releaseRefresh = resolve;
  });
  const refreshRoute = "**/participants/" + participantId + "/onboarding";
  await page.route(refreshRoute, async (route) => {
    refreshStarted();
    await refreshReleased;
    await route.continue();
  });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await refreshPending;
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Save", exact: true }),
  ).toBeDisabled();
  releaseRefresh();
  await expect(dialog).toHaveCount(0);
  await page.unroute(refreshRoute);
  await page.getByRole("button", { name: "Assignment", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Assign participant" });
  await dialog
    .getByRole("combobox", { name: "Priority", exact: true })
    .selectOption("URGENT");
  await dialog
    .getByLabel("Next action", { exact: true })
    .fill("Arrange participant follow-up");
  await dialog.getByLabel("Due (Ghana time)").fill("2026-10-02T09:00");
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic action assignment");
  await save(page, "Assign participant");
  await page.screenshot({
    path: info.outputPath("participant-review.png"),
    fullPage: true,
  });
  await expect(
    page.getByRole("tab", { name: "Sensitive", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Supply Dashboard", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Job ready", exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Loading...", { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("supply-dashboard.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Job ready", exact: false }).click();
  await expect(page.getByRole("button", { name, exact: false })).toBeVisible();
  await page.getByRole("button", { name: "My Work", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Overdue", exact: true })
      .getByText(name, { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("supply-work.png"),
    fullPage: true,
  });
  await page
    .getByRole("region", { name: "Overdue", exact: true })
    .getByRole("button", { name: name, exact: false })
    .click();
  await page.getByRole("tab", { name: "Consent", exact: true }).click();
  await page.getByRole("button", { name: "Withdraw", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Withdraw consent" });
  await dialog
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic participant withdrawal");
  await save(page, "Withdraw consent");
  await expect(page.getByText("Blocked", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("Matching participant reader has no onboarding or sensitive editing access", async ({
  page,
}, info) => {
  await login(page, "matching@example.org");
  await page.getByRole("button", { name: "Participants", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "New participant", exact: true }),
  ).toHaveCount(0);
  const response = await page.request.get("/api/v1/participants");
  expect(response.status()).toBe(200);
  const row = (await response.json()).items[0];
  expect(row).toBeTruthy();
  await page.getByRole("button", { name: row.full_name, exact: false }).click();
  await expect(
    page.getByRole("button", { name: "Assignment", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Sensitive", exact: true }),
  ).toHaveCount(0);
  expect(
    (
      await page.request.get("/api/v1/participants/" + row.id + "/sensitive")
    ).status(),
  ).toBe(403);
  await page.screenshot({
    path: info.outputPath("participant-readonly.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("Supply staff reviews advisory CV parser suggestions without automatic overwrite", async ({
  page,
}, info) => {
  await login(page);
  await navigate(page, "Participants");
  const name = "Synthetic CV Fixture " + info.project.name;
  await page.getByLabel("Search", { exact: true }).fill(name);
  await page.getByRole("button", { name, exact: false }).click();
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  const participant = (
    await (
      await page.request.get(
        "/api/v1/participants?q=" + encodeURIComponent(name),
      )
    ).json()
  ).items[0];
  const documents = (
    await (
      await page.request.get(
        `/api/v1/participants/${participant.id}/cv/versions`,
      )
    ).json()
  ).items;
  const document = documents.find(
    (item: { scan_status: string }) => item.scan_status === "AVAILABLE",
  );
  let parsed = false;
  let reviewed = false;
  const result = () => ({
    id: "10000000-0000-4000-8000-000000000002",
    job_id: "10000000-0000-4000-8000-000000000001",
    schema_version: "1",
    provider: "SYNTHETIC_BROWSER_PARSER",
    model: "browser-v1",
    review_status: reviewed ? "APPROVED" : "PENDING_REVIEW",
    suggestions: [
      { field: "first_name", value: "Ama", confidence: 0.98 },
      {
        field: "skills",
        value: ["Excel", "Customer service"],
        confidence: 0.84,
      },
    ],
    reviews: reviewed
      ? [
          {
            id: "10000000-0000-4000-8000-000000000003",
            field: "first_name",
            decision: "APPROVE",
            original_value: "Ama",
            approved_value: "Ama",
            confidence: 0.98,
            reason: null,
          },
          {
            id: "10000000-0000-4000-8000-000000000004",
            field: "skills",
            decision: "REJECT",
            original_value: ["Excel", "Customer service"],
            approved_value: null,
            confidence: 0.84,
            reason: null,
          },
        ]
      : [],
  });
  const job = () => ({
    id: "10000000-0000-4000-8000-000000000001",
    document_id: document.id,
    document_version: 1,
    status: "SUCCEEDED",
    provider: "SYNTHETIC_BROWSER_PARSER",
    model: "browser-v1",
    input_categories: ["contact", "employment", "skills"],
    attempt_count: 1,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    error_code: null,
    error_message: null,
    version: 2,
    result: result(),
  });
  await page.route(`**/api/v1/cv/${document.id}/parser-jobs`, (route) =>
    route.fulfill({ json: { items: parsed ? [job()] : [] } }),
  );
  await page.route(`**/api/v1/cv/${document.id}/parse`, (route) => {
    parsed = true;
    return route.fulfill({ status: 201, json: job() });
  });
  await page.route(
    "**/api/v1/cv-parser/results/10000000-0000-4000-8000-000000000002/review",
    async (route) => {
      const body = route.request().postDataJSON();
      expect(body.decisions).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ field: "first_name", decision: "APPROVE" }),
          expect.objectContaining({ field: "skills", decision: "REJECT" }),
        ]),
      );
      reviewed = true;
      await route.fulfill({ json: result() });
    },
  );
  await page
    .getByRole("button", { name: "Parser review", exact: true })
    .click();
  await page.getByRole("button", { name: "Parse CV", exact: true }).click();
  await expect(page.getByText("98% confidence", { exact: true })).toBeVisible();
  const choices = page.getByLabel("Decision", { exact: true });
  await choices.nth(0).selectOption("APPROVE");
  await choices.nth(1).selectOption("REJECT");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(
    page.getByText("approved | SYNTHETIC_BROWSER_PARSER", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("approve", { exact: true })).toBeVisible();
  await expect(page.getByText("reject", { exact: true })).toBeVisible();
  await page.screenshot({
    path: info.outputPath("cv-parser-review.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
