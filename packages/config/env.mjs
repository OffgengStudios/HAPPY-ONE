import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import dotenv from "dotenv";

export function loadProjectEnvironment(
  projectRoot,
  appDirectory,
  environment = process.env,
) {
  const selectedFile = environment.HAPPY_ENV_FILE;
  const files = selectedFile
    ? [
        isAbsolute(selectedFile)
          ? selectedFile
          : resolve(projectRoot, selectedFile),
      ]
    : [
        resolve(appDirectory, ".env.local"),
        resolve(appDirectory, ".env"),
        resolve(projectRoot, ".env"),
      ];

  if (selectedFile && !existsSync(files[0])) {
    throw new Error("HAPPY_ENV_FILE does not exist.");
  }
  for (const path of files) {
    dotenv.config({
      path,
      processEnv: environment,
      override: false,
      quiet: true,
    });
  }
  environment.NEXT_PUBLIC_APP_ENV ??= environment.APP_ENV ?? "development";
  return environment;
}
