import { cpSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import config from "./next.config.mjs";

const directory = dirname(fileURLToPath(import.meta.url));
if (config.output === "standalone") {
  const target = join(directory, ".next/standalone/apps/web");
  cpSync(join(directory, ".next/static"), join(target, ".next/static"), {
    recursive: true,
  });
  if (existsSync(join(directory, "public"))) {
    cpSync(join(directory, "public"), join(target, "public"), {
      recursive: true,
    });
  }
  await import(pathToFileURL(join(target, "server.js")).href);
} else {
  const require = createRequire(import.meta.url);
  const child = spawn(
    process.execPath,
    [
      require.resolve("next/dist/bin/next"),
      "start",
      "--hostname",
      process.env.HOSTNAME ?? "127.0.0.1",
      "--port",
      process.env.PORT ?? "3000",
    ],
    { stdio: "inherit" },
  );
  process.on("SIGTERM", () => child.kill("SIGTERM"));
  process.on("SIGINT", () => child.kill("SIGINT"));
  child.on("exit", (code) => {
    process.exitCode = code ?? 1;
  });
}
