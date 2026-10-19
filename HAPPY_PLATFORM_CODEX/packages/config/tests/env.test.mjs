import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { loadProjectEnvironment } from "../env.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "happy-env-"));
  const app = join(root, "apps", "web");
  mkdirSync(app, { recursive: true });
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return { root, app };
}

test("root values are available, including quoted JSON and public API URLs", (t) => {
  const { root, app } = fixture(t);
  writeFileSync(
    join(root, ".env"),
    'NEXT_PUBLIC_API_BASE_URL=https://api.example/api/v1\nAPP_ENV=staging\nAPI_CORS_ORIGINS=["https://app.example"]\n',
  );
  const values = loadProjectEnvironment(root, app, {});
  assert.equal(values.NEXT_PUBLIC_API_BASE_URL, "https://api.example/api/v1");
  assert.equal(values.NEXT_PUBLIC_APP_ENV, "staging");
  assert.equal(values.API_CORS_ORIGINS, '["https://app.example"]');
});

test("process values override app values, which override root values", (t) => {
  const { root, app } = fixture(t);
  writeFileSync(join(root, ".env"), "VALUE=root\nOTHER=root\n");
  writeFileSync(join(app, ".env"), "VALUE=app\nOTHER=app\n");
  const values = loadProjectEnvironment(root, app, { VALUE: "process" });
  assert.equal(values.VALUE, "process");
  assert.equal(values.OTHER, "app");
});

test("an explicit staging file excludes development files", (t) => {
  const { root, app } = fixture(t);
  writeFileSync(join(root, ".env"), "VALUE=development\nDEV_SECRET=private\n");
  writeFileSync(join(app, ".env.local"), "VALUE=local\n");
  writeFileSync(join(root, ".env.staging"), "VALUE=staging\nAPP_ENV=staging\n");
  const values = loadProjectEnvironment(root, app, {
    HAPPY_ENV_FILE: ".env.staging",
  });
  assert.equal(values.VALUE, "staging");
  assert.equal(values.DEV_SECRET, undefined);
});

test("a missing explicitly selected environment fails", (t) => {
  const { root, app } = fixture(t);
  assert.throws(
    () => loadProjectEnvironment(root, app, { HAPPY_ENV_FILE: ".env.missing" }),
    /does not exist/,
  );
});
