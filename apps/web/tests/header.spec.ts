import { expect, type Page, test } from "@playwright/test";
import { signOut } from "./navigation";

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

async function csrf(page: Page) {
  return {
    Origin: new URL(page.url()).origin,
    "X-CSRF-Token": (await page.context().cookies()).find(
      (cookie) => cookie.name === "happy_csrf",
    )!.value,
  };
}

async function search(page: Page, q: string) {
  await page
    .getByRole("button", { name: "Global search", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Search", exact: true });
  await expect(dialog.getByLabel("Search records")).toBeFocused();
  await dialog.getByLabel("Search records").fill(q);
  return dialog;
}

test("the account menu supports keyboard navigation, security and sign-out recovery", async ({
  page,
}, info) => {
  await login(page);
  const trigger = page.getByRole("button", {
    name: "Account menu",
    exact: true,
  });
  const menu = page.getByRole("menu", { name: "Account", exact: true });
  await trigger.click();
  await expect(
    menu.getByText("admin@example.org", { exact: true }),
  ).toBeVisible();
  const security = menu.getByRole("menuitem", {
    name: "Account security",
    exact: true,
  });
  const logout = menu.getByRole("menuitem", { name: "Sign out", exact: true });
  await expect(security).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(logout).toBeFocused();
  await page.keyboard.press("Home");
  await expect(security).toBeFocused();
  await page.keyboard.press("End");
  await expect(logout).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await security.click();
  await expect(
    page.getByRole("heading", { name: "Active sessions", exact: true }),
  ).toBeVisible();
  await trigger.click();
  await page.route("**/api/v1/auth/logout", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "Temporarily unavailable." } }),
    }),
  );
  await logout.click();
  await expect(menu.getByRole("alert")).toHaveText(
    "Unable to sign out. Try again.",
  );
  await expect(logout).toBeEnabled();
  await expect(menu).toBeVisible();
  await page.screenshot({
    path: info.outputPath("account-menu.png"),
    fullPage: false,
  });
  await expect(menu).toBeVisible();
  await page.unroute("**/api/v1/auth/logout");
  await page.keyboard.press("Escape");
  await signOut(page);
  await expect(menu).toHaveCount(0);
});

test("the profile popover fits narrow screens and dismisses outside or on resize", async ({
  page,
  isMobile,
}) => {
  await login(page);
  if (isMobile) await page.setViewportSize({ width: 320, height: 700 });
  const trigger = page.getByRole("button", {
    name: "Account menu",
    exact: true,
  });
  const menu = page.getByRole("menu", { name: "Account", exact: true });
  await trigger.click();
  const box = (await menu.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(
    await menu.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  const outside = {
    x: page.viewportSize()!.width / 2,
    y: page.viewportSize()!.height - 128,
  };
  expect(
    await menu.evaluate((element, point) => {
      const target = document.elementFromPoint(point.x, point.y);
      return !!target && !element.contains(target) && !target.closest("header");
    }, outside),
  ).toBe(true);
  await page.mouse.click(outside.x, outside.y);
  await expect(menu).not.toBeVisible();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  await page.setViewportSize({ width: 1000, height: 800 });
  await expect(menu).not.toBeVisible();
});

test("grouped search opens the existing UUID-backed records without changing workspace", async ({
  page,
}, info) => {
  await login(page, "matching@example.org");
  const queries = [
    {
      q: "Synthetic CV Fixture " + info.project.name,
      group: "Participants",
      path: "participants",
    },
    {
      q: "Synthetic Browser Employer",
      group: "Employers",
      path: "organizations",
    },
    { q: "Read-only Browser Vacancy", group: "Vacancies", path: "vacancies" },
  ];
  for (const query of queries) {
    const responseEvent = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/search") &&
        response.request().method() === "POST",
    );
    const dialog = await search(page, query.q);
    const response = await responseEvent;
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toBe("no-store");
    expect(response.request().postDataJSON()).toEqual({ q: query.q, limit: 5 });
    const body = await response.json();
    const entity =
      query.path === "participants"
        ? "PARTICIPANT"
        : query.path === "organizations"
          ? "ORGANIZATION"
          : "VACANCY";
    const row = body.groups[entity].items[0];
    expect(row).toBeTruthy();
    const read = page.waitForResponse((result) =>
      result
        .url()
        .endsWith(
          "/" +
            query.path +
            "/" +
            row.id +
            (query.path === "participants" ? "/onboarding" : ""),
        ),
    );
    await dialog
      .getByRole("region", { name: query.group, exact: true })
      .getByRole("button", { name: row.label, exact: false })
      .click();
    expect((await read).status()).toBe(200);
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: row.label, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Workspace content", exact: true }),
    ).toBeFocused();
    expect(new URL(page.url()).search).toBe("");
    await expect(
      page.getByRole("button", { name: "New participant", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "New employer", exact: true }),
    ).toHaveCount(0);
  }
  await page.screenshot({
    path: info.outputPath("search-readonly-record.png"),
    fullPage: true,
  });
});

test("search pages are bounded, replace results and retain earlier cursors", async ({
  page,
}, info) => {
  await login(page);
  const q = "Lookup " + info.project.name;
  for (let index = 0; index < 7; index++) {
    const response = await page.request.post("/api/v1/participants", {
      headers: await csrf(page),
      data: {
        first_name: "Lookup",
        surname: info.project.name + " " + index,
        phone_raw:
          "024" +
          (info.project.name === "mobile" ? "82" : "81") +
          String(index).padStart(5, "0"),
        community: "Synthetic lookup",
        // Deliberately distinct synthetic people with similar names and location.
        duplicate_acknowledged: true,
      },
    });
    expect(response.status()).toBe(201);
  }
  const dialog = await search(page, q);
  const group = dialog.getByRole("region", {
    name: "Participants",
    exact: true,
  });
  const rows = group.getByRole("button", { name: q, exact: false });
  await expect(rows).toHaveCount(5);
  const firstPage = await rows.allTextContents();
  const previous = group.getByRole("button", {
    name: "Previous participants",
    exact: true,
  });
  await expect(previous).toBeDisabled();
  const nextResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/search") &&
      response.request().postDataJSON()?.entities?.[0] === "PARTICIPANT",
  );
  await group
    .getByRole("button", { name: "Next participants", exact: true })
    .click();
  const next = await nextResponse;
  expect(next.request().postDataJSON().limit).toBe(5);
  expect(next.request().postDataJSON().cursors.PARTICIPANT).toBeTruthy();
  await expect(rows).toHaveCount(2);
  expect(
    (await rows.allTextContents()).some((text) => firstPage.includes(text)),
  ).toBe(false);
  await expect(
    group.getByRole("button", { name: "Next participants", exact: true }),
  ).toBeDisabled();
  await previous.click();
  await expect(rows).toHaveCount(5);
  expect(await rows.allTextContents()).toEqual(firstPage);
  await dialog.getByLabel("Search records").fill(q + " ");
  await expect(rows).toHaveCount(5);
  expect(
    await page.evaluate(() =>
      Object.values(localStorage).some((value) => value.includes("Lookup")),
    ),
  ).toBe(false);
  await page.screenshot({
    path: info.outputPath("search-results.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Global search", exact: true }),
  ).toBeFocused();
});

test("changed search text aborts older responses and failed searches can be retried", async ({
  page,
}) => {
  await login(page);
  let started!: () => void;
  let release!: () => void;
  const firstStarted = new Promise<void>((resolve) => {
    started = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  let oldCompleted!: () => void;
  const completion = new Promise<void>((resolve) => {
    oldCompleted = resolve;
  });
  await page.route("**/api/v1/search", async (route) => {
    const q = route.request().postDataJSON().q;
    if (q === "older query") {
      started();
      await released;
      await route
        .fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            groups: {
              PARTICIPANT: {
                items: [
                  {
                    entity_type: "PARTICIPANT",
                    id: "00000000-0000-0000-0000-000000000001",
                    code: "SYNTHETIC",
                    label: "Stale result",
                    context: null,
                  },
                ],
                next_cursor: null,
              },
            },
          }),
        })
        .catch(() => undefined);
      oldCompleted();
    } else await route.continue();
  });
  const dialog = await search(page, "older query");
  await firstStarted;
  await dialog.getByLabel("Search records").fill("Synthetic CV Fixture");
  await expect(
    dialog.getByRole("region", { name: "Participants", exact: true }),
  ).toBeVisible();
  release();
  await completion;
  await expect(dialog.getByText("Stale result", { exact: true })).toHaveCount(
    0,
  );
  await page.unroute("**/api/v1/search");
  await page.route("**/api/v1/search", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { message: "Search is temporarily unavailable." },
      }),
    }),
  );
  await dialog.getByLabel("Search records").fill("Browser");
  await expect(dialog.getByRole("alert")).toHaveText(
    "Search is temporarily unavailable.",
  );
  await page.unroute("**/api/v1/search");
  await dialog
    .getByRole("button", { name: "Retry search", exact: true })
    .click();
  await expect(
    dialog.getByRole("region", { name: "Vacancies", exact: true }),
  ).toBeVisible();
  await expect(dialog.getByRole("alert")).toHaveCount(0);
});

test("search only reveals permitted groups and disappears on real session expiry", async ({
  page,
}) => {
  await login(page, "marketing@example.org");
  const dialog = await search(page, "Browser");
  await expect(
    dialog.getByRole("region", { name: "Vacancies", exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("region", { name: "Participants", exact: true }),
  ).toHaveCount(0);
  await expect(
    dialog.getByRole("region", { name: "Employers", exact: true }),
  ).toHaveCount(0);
  expect(
    (
      await page.request.post("/api/v1/search", {
        headers: await csrf(page),
        data: { q: "Browser", entities: ["PARTICIPANT"] },
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.post("/api/v1/auth/logout", {
        headers: await csrf(page),
      })
    ).status(),
  ).toBe(204);
  await dialog.getByLabel("Search records").fill("expired session");
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("menu", { name: "Account", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Global search", exact: true }),
  ).toHaveCount(0);
});
