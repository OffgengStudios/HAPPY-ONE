const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require(
  require.resolve("@playwright/test", {
    paths: [path.join(__dirname, "../HAPPY_PLATFORM_CODEX/apps/web")],
  }),
);
const collector =
  process.env.UNIJAY_REPOSITORY ||
  path.resolve(__dirname, "../../UNIJAY-FASHION-DATA-COLLECTION");
fs.mkdirSync(path.join(__dirname, "../.local/unijay-consolidation"), {
  recursive: true,
});
const requests = [];
const notice = {
  source_system: "UNIJAY_FASHION",
  accepting_submissions: true,
  privacy_notice: "Synthetic browser notice",
  privacy_notice_version: "SYNTHETIC-1",
  training_interests: {
    CAREER_READINESS: "Career Readiness",
    SOFT_SKILLS: "Soft skills",
  },
};
let apiReady = true;
const server = http.createServer((req, res) => {
  if (req.url === "/config.js") {
    res.setHeader("Content-Type", "text/javascript");
    return res.end(
      "window.UNIJAY_CONFIG=" +
        JSON.stringify({
          apiBaseUrl: "http://127.0.0.1:" + server.address().port,
        }),
    );
  }
  if (req.url === "/api/v1/participant-intake/config") {
    res.setHeader("Content-Type", "application/json");
    return res.end(
      JSON.stringify({ ...notice, accepting_submissions: apiReady }),
    );
  }
  if (req.url === "/api/v1/participant-intake") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      const match = body.match(/name="payload"\r\n\r\n([^\r]+)/);
      assert.ok(match);
      requests.push(JSON.parse(match[1]));
      res.setHeader("Content-Type", "application/json");
      res.statusCode = requests.length % 2 === 1 ? 503 : 202;
      res.end(
        JSON.stringify(
          res.statusCode === 202
            ? {
                receipt_id: "00000000-0000-4000-8000-000000000001",
                status: "RECEIVED",
              }
            : { code: "TEMPORARY_FAILURE" },
        ),
      );
    });
    return;
  }
  const filename = path.join(
    collector,
    "data-collection-tool",
    req.url === "/" ? "index.html" : req.url.slice(1),
  );
  if (
    !filename.startsWith(
      path.join(collector, "data-collection-tool") + path.sep,
    )
  ) {
    res.statusCode = 404;
    return res.end();
  }
  fs.readFile(filename, (error, content) => {
    if (error) {
      res.statusCode = 404;
      return res.end();
    }
    res.setHeader(
      "Content-Type",
      filename.endsWith(".js")
        ? "text/javascript"
        : filename.endsWith(".css")
          ? "text/css"
          : filename.endsWith(".html")
            ? "text/html"
            : "image/svg+xml",
    );
    res.end(content);
  });
});
(async () => {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    const installed =
      "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
    browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_CHANNEL
        ? { channel: process.env.PLAYWRIGHT_CHANNEL }
        : fs.existsSync(installed)
          ? { executablePath: installed }
          : {}),
    });
    for (const [name, viewport] of [
      ["desktop", { width: 1440, height: 1000 }],
      ["mobile", { width: 390, height: 844 }],
    ]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("http://127.0.0.1:" + server.address().port);
      await page.locator("#submitButton").waitFor({ state: "visible" });
      await page.waitForFunction(
        () => !document.querySelector("#submitButton").disabled,
      );
      assert.equal(await page.locator("input[type=password]").count(), 0);
      assert.equal(
        await page.locator("#privacyNotice").innerText(),
        notice.privacy_notice,
      );
      await page.locator("#firstName").fill("Synthetic");
      await page.locator("#otherNames").fill("Browser");
      await page.locator("#surname").fill(name);
      await page.locator("#phone").fill("0241234567");
      await page.locator("#dateOfBirth").fill("1990-01-02");
      await page.locator("#ghanaCard").fill("GHA-123456789-0");
      await page.locator("#location").fill("Synthetic community");
      await page.locator("#careerReadiness").check();
      await page.locator("#consent").check();
      await page.screenshot({
        path: path.join(
          __dirname,
          "../.local/unijay-consolidation/unijay-form-" + name + ".png",
        ),
        fullPage: true,
      });
      await page.locator("#submitButton").click();
      await page.locator("#statusMessage.error").waitFor();
      await page.locator("#submitButton").click();
      await page.locator("#successCard").waitFor({ state: "visible" });
      assert.deepEqual(requests.at(-1), requests.at(-2));
      assert.equal(requests.at(-1).identity.government_id, "GHA-123456789-0");
      assert.equal(requests.at(-1).consent.notice_version, "SYNTHETIC-1");
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
      assert.deepEqual(errors, []);
      await page.screenshot({
        path: path.join(
          __dirname,
          "../.local/unijay-consolidation/unijay-" + name + ".png",
        ),
        fullPage: true,
      });
      await context.close();
    }
    apiReady = false;
    const page = await browser.newPage();
    await page.goto("http://127.0.0.1:" + server.address().port);
    await page.waitForFunction(() =>
      document
        .querySelector("#privacyNotice")
        .textContent.includes("temporarily unavailable"),
    );
    assert.equal(await page.locator("#submitButton").isDisabled(), true);
    await page.close();
    console.log(
      "3 browser scenarios passed: desktop/mobile direct multipart retry and unavailable-notice fail closed.",
    );
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
